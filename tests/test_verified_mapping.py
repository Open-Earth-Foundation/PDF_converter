"""Unit tests for verified field mapping utilities."""

import pytest
from uuid import uuid4

from extraction.utils.verified_field import VerifiedField
from extraction.schemas_verified import VerifiedCityTarget, VerifiedEmissionRecord
from extraction.utils.verified_utils import map_verified_to_db


class TestMapVerifiedToDb:
    """Test map_verified_to_db function."""

    def test_map_valid_verified_fields(self):
        """Test mapping verified fields with valid quotes."""
        source_text = "Target: reduce emissions by 80% by 2030"

        city_target = VerifiedCityTarget(
            description="Emission reduction target",
            targetYear=VerifiedField[str](
                value="2030",
                quote="by 2030",
                confidence=0.95,
            ),
            targetValue=VerifiedField[str](
                value="80",
                quote="80%",
                confidence=0.95,
            ),
            status=VerifiedField[str](
                value="Set",
                quote="Target: reduce emissions",
                confidence=0.8,
            ),
        )

        output_dict, errors = map_verified_to_db(city_target, source_text)

        # Check output format
        assert "description" in output_dict
        assert output_dict["description"] == "Emission reduction target"

        # Check scalar values extracted
        assert "targetYear" in output_dict
        assert output_dict["targetYear"] == 2030

        assert "targetValue" in output_dict
        assert output_dict["targetValue"] == "80"

        assert "status" in output_dict
        assert output_dict["status"] == "Set"

        # Check proofs in misc
        assert "misc" in output_dict
        assert "targetYear_proof" in output_dict["misc"]
        assert "targetValue_proof" in output_dict["misc"]
        assert "status_proof" in output_dict["misc"]

        # Check proof structure
        proof = output_dict["misc"]["targetYear_proof"]
        assert proof["quote"] == "by 2030"
        assert proof["confidence"] == 0.95

        # Should be no errors
        assert len(errors) == 0

    def test_map_with_invalid_quote(self):
        """Test mapping with quote not in source - should reject."""
        source_text = "Target: reduce emissions by 2030"

        city_target = VerifiedCityTarget(
            description="Emission reduction target",
            targetYear=VerifiedField[str](
                value="2030",
                quote="by 2030",
                confidence=0.95,
            ),
            targetValue=VerifiedField[str](
                value="80",
                quote="80%",  # This quote is NOT in source
                confidence=0.95,
            ),
            status=VerifiedField[str](
                value="Set",
                quote="Target:",
                confidence=0.8,
            ),
        )

        output_dict, errors = map_verified_to_db(city_target, source_text)

        # Should have error for targetValue
        assert len(errors) > 0
        assert "targetValue" in errors or "target_value" in errors

        # Output should still have some data but with limited content
        # (validation failed, so fewer fields)

    def test_map_with_none_value_valid_quote(self):
        """Test mapping with None value but valid quote."""
        source_text = "Target set for 2030 with value 50. Status set. No baseline year specified"

        city_target = VerifiedCityTarget(
            description="Target without baseline",
            targetYear=VerifiedField[str](
                value="2030",
                quote="2030",
                confidence=0.95,
            ),
            targetValue=VerifiedField[str](
                value="50",
                quote="50",
                confidence=0.9,
            ),
            baselineYear=VerifiedField[str](
                value=None,
                quote="No baseline year specified",
                confidence=0.9,
            ),
            status=VerifiedField[str](
                value="Set",
                quote="set",
                confidence=0.8,
            ),
        )

        output_dict, errors = map_verified_to_db(city_target, source_text)

        # Should have no errors (quote is found)
        assert len(errors) == 0

        # baselineYear should be null in output
        assert output_dict.get("baselineYear") is None

        # But proof should still exist
        assert "misc" in output_dict
        assert "baselineYear_proof" in output_dict["misc"]

    def test_map_preserves_non_verified_fields(self):
        """Test that non-verified fields are preserved."""
        source_text = "Target: reduce by 80% by 2030"

        city_target = VerifiedCityTarget(
            description="Important climate target",
            targetYear=VerifiedField[str](
                value="2030",
                quote="2030",
                confidence=0.95,
            ),
            targetValue=VerifiedField[str](
                value="80",
                quote="80%",
                confidence=0.95,
            ),
            status=VerifiedField[str](
                value="Set",
                quote="Target:",
                confidence=0.8,
            ),
            notes="This is an important note",
        )

        output_dict, errors = map_verified_to_db(city_target, source_text)

        # Non-verified fields should be preserved
        assert output_dict.get("description") == "Important climate target"
        assert output_dict.get("notes") == "This is an important note"

    def test_map_merges_with_existing_misc(self):
        """Test that proofs are merged with existing misc data."""
        source_text = "Target year 2030"

        city_target = VerifiedCityTarget(
            description="Target",
            targetYear=VerifiedField[str](
                value="2030",
                quote="2030",
                confidence=0.95,
            ),
            targetValue=VerifiedField[str](
                value="50",
                quote="50",
                confidence=0.9,
            ),
            status=VerifiedField[str](
                value="Set",
                quote="Target",
                confidence=0.8,
            ),
            misc={"custom_field": "custom_value"},
        )

        output_dict, errors = map_verified_to_db(city_target, source_text)

        # Existing misc should be preserved
        assert output_dict["misc"]["custom_field"] == "custom_value"

        # Proofs should be added
        assert "targetYear_proof" in output_dict["misc"]

    def test_map_emission_record(self):
        """Test mapping VerifiedEmissionRecord."""
        source_text = "Year 2019, Scope 1, CO2e emissions 5250 tCO2e"

        emission_record = VerifiedEmissionRecord(
            year=VerifiedField[str](
                value="2019",
                quote="Year 2019",
                confidence=0.95,
            ),
            scope="Scope 1",
            ghgType="CO2e",
            value=VerifiedField[str](
                value="5250",
                quote="5250",
                confidence=0.95,
            ),
            unit="tCO2e",
        )

        output_dict, errors = map_verified_to_db(emission_record, source_text)

        # Check no errors
        assert len(errors) == 0

        # Check output
        assert output_dict["year"] == 2019
        assert output_dict["scope"] == "Scope 1"
        assert output_dict["value"] == 5250

        # Check proofs
        assert "misc" in output_dict
        assert "year_proof" in output_dict["misc"]
        assert "value_proof" in output_dict["misc"]

    def test_map_returns_errors_dict(self):
        """Test that errors dict contains field names and messages."""
        source_text = "No matching quotes here"

        city_target = VerifiedCityTarget(
            description="Target",
            targetYear=VerifiedField[str](
                value="2030",
                quote="not in source",
                confidence=0.95,
            ),
            targetValue=VerifiedField[str](
                value="80",
                quote="also not here",
                confidence=0.95,
            ),
            status=VerifiedField[str](
                value="Set",
                quote="not here either",
                confidence=0.8,
            ),
        )

        output_dict, errors = map_verified_to_db(city_target, source_text)

        # Should have multiple errors
        assert len(errors) >= 1

        # Errors should be keyed by field name
        for field_name in errors:
            assert isinstance(field_name, str)
            assert isinstance(errors[field_name], str)
            assert "quote" in errors[field_name].lower() or "not found" in errors[field_name].lower()
