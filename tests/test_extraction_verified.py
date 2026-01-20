"""Integration tests for extraction with verified fields and quote validation."""

import pytest
import json
from typing import Type
from pydantic import BaseModel

from extraction.utils.verified_field import VerifiedField
from extraction.schemas_verified import VerifiedCityTarget, VerifiedEmissionRecord
from extraction.utils.data_utils import parse_record_instances


class FakeToolCall:
    """Fake tool call for testing."""

    def __init__(self, arguments: str, call_id: str = "test-call-1"):
        self.arguments = arguments
        self.id = call_id
        self.name = "record_instances"


class TestExtractedWithVerifiedFields:
    """Integration tests for extraction with verified fields."""

    def test_parse_valid_city_target_records(self):
        """Test parsing valid city target records with verified fields."""
        source_text = """
        Climate Targets:
        - Target 1: 80% reduction by 2030
        - Baseline: 2019
        - Status: On track
        """

        raw_items = [
            {
                "description": "Emission reduction target",
                "targetYear": {
                    "value": "2030",
                    "quote": "by 2030",
                    "confidence": 0.95,
                },
                "targetValue": {
                    "value": "80",
                    "quote": "80%",
                    "confidence": 0.95,
                },
                "status": {
                    "value": "On track",
                    "quote": "On track",
                    "confidence": 0.9,
                },
            }
        ]

        call = FakeToolCall(json.dumps({"items": raw_items}))
        seen_hashes = set()
        stored = []

        result, added = parse_record_instances(
            call,
            VerifiedCityTarget,
            seen_hashes,
            stored,
            source_text=source_text,
        )

        # Should accept the record
        assert result["accepted"] == 1
        assert result["status"] == "ok"
        assert added is True
        assert len(stored) == 1

        # Check output format (scalars + proofs in misc)
        record = stored[0]
        assert record["description"] == "Emission reduction target"
        assert record["targetYear"] == 2030
        assert record["targetValue"] == "80"
        assert record["status"] == "On track"

        # Check proofs
        assert "misc" in record
        assert "targetYear_proof" in record["misc"]
        assert record["misc"]["targetYear_proof"]["quote"] == "by 2030"
        assert record["misc"]["targetYear_proof"]["confidence"] == 0.95

    def test_parse_rejects_record_with_invalid_quote(self):
        """Test that record is rejected if quote not in source."""
        source_text = "Only this text is available in the source document"

        raw_items = [
            {
                "description": "Emission reduction target",
                "targetYear": {
                    "value": "2030",
                    "quote": "by 2030",  # NOT in source
                    "confidence": 0.95,
                },
                "targetValue": {
                    "value": "80",
                    "quote": "80%",  # NOT in source
                    "confidence": 0.95,
                },
                "status": {
                    "value": "On track",
                    "quote": "On track",  # NOT in source
                    "confidence": 0.9,
                },
            }
        ]

        call = FakeToolCall(json.dumps({"items": raw_items}))
        seen_hashes = set()
        stored = []

        result, added = parse_record_instances(
            call,
            VerifiedCityTarget,
            seen_hashes,
            stored,
            source_text=source_text,
        )

        # Should reject the record
        assert result["accepted"] == 0
        assert result["status"] == "error" or (result["status"] == "partial" and len(result["errors"]) > 0)
        assert added is False
        assert len(stored) == 0

    def test_parse_multiple_records_mixed_validity(self):
        """Test parsing multiple records with some valid and some invalid."""
        source_text = "Valid: 80% by 2030. Status: On track"

        raw_items = [
            {
                "description": "Valid target",
                "targetYear": {
                    "value": "2030",
                    "quote": "by 2030",  # In source
                    "confidence": 0.95,
                },
                "targetValue": {
                    "value": "80",
                    "quote": "80%",  # In source
                    "confidence": 0.95,
                },
                "status": {
                    "value": "On track",
                    "quote": "On track",  # In source
                    "confidence": 0.9,
                },
            },
            {
                "description": "Invalid target",
                "targetYear": {
                    "value": "2025",
                    "quote": "by 2025",  # NOT in source
                    "confidence": 0.95,
                },
                "targetValue": {
                    "value": "50",
                    "quote": "50%",  # NOT in source
                    "confidence": 0.95,
                },
                "status": {
                    "value": "Planned",
                    "quote": "Planned",  # NOT in source
                    "confidence": 0.8,
                },
            },
        ]

        call = FakeToolCall(json.dumps({"items": raw_items}))
        seen_hashes = set()
        stored = []

        result, added = parse_record_instances(
            call,
            VerifiedCityTarget,
            seen_hashes,
            stored,
            source_text=source_text,
        )

        # Should accept 1 and reject 1
        assert result["accepted"] == 1
        assert len(result["errors"]) > 0
        assert result["status"] == "partial"
        assert added is True
        assert len(stored) == 1

    def test_parse_with_none_value_valid_quote(self):
        """Test parsing record with None value but valid quote."""
        source_text = "Target 80% by 2030. Status: Set. No baseline specified in the document."

        raw_items = [
            {
                "description": "Target without baseline",
                "targetYear": {
                    "value": "2030",
                    "quote": "2030",
                    "confidence": 0.95,
                },
                "targetValue": {
                    "value": "80",
                    "quote": "80%",
                    "confidence": 0.95,
                },
                "baselineYear": {
                    "value": None,
                    "quote": "No baseline specified",
                    "confidence": 0.9,
                },
                "status": {
                    "value": "Set",
                    "quote": "Set",
                    "confidence": 0.8,
                },
            }
        ]

        call = FakeToolCall(json.dumps({"items": raw_items}))
        seen_hashes = set()
        stored = []

        result, added = parse_record_instances(
            call,
            VerifiedCityTarget,
            seen_hashes,
            stored,
            source_text=source_text,
        )

        # Should accept (quote is in source)
        assert result["accepted"] == 1
        assert result["status"] == "ok"
        assert len(stored) == 1

        record = stored[0]
        assert record["baselineYear"] is None
        assert "baselineYear_proof" in record["misc"]

    def test_parse_emission_records_with_verified_fields(self):
        """Test parsing emission records with verified year and value."""
        source_text = "Emission Inventory: 2019 emissions 5250 tCO2e Scope 1"

        raw_items = [
            {
                "year": {
                    "value": "2019",
                    "quote": "2019",
                    "confidence": 0.95,
                },
                "scope": "Scope 1",
                "ghgType": "CO2e",
                "value": {
                    "value": "5250",
                    "quote": "5250",
                    "confidence": 0.95,
                },
                "unit": "tCO2e",
            }
        ]

        call = FakeToolCall(json.dumps({"items": raw_items}))
        seen_hashes = set()
        stored = []

        result, added = parse_record_instances(
            call,
            VerifiedEmissionRecord,
            seen_hashes,
            stored,
            source_text=source_text,
        )

        # Should accept
        assert result["accepted"] == 1
        assert result["status"] == "ok"
        assert len(stored) == 1

        record = stored[0]
        assert record["year"] == 2019
        assert record["value"] == 5250
        assert record["scope"] == "Scope 1"
        assert "misc" in record
        assert "year_proof" in record["misc"]
        assert "value_proof" in record["misc"]

    def test_parse_without_source_text_uses_standard_validation(self):
        """Test that parsing without source text skips quote validation."""
        # No source text provided - should use standard validation
        raw_items = [
            {
                "description": "Target without quotes",
                "targetYear": {
                    "value": "2030",
                    "quote": "by 2030",
                    "confidence": 0.95,
                },
                "targetValue": {
                    "value": "80",
                    "quote": "80%",
                    "confidence": 0.95,
                },
                "status": {
                    "value": "Set",
                    "quote": "Set",
                    "confidence": 0.8,
                },
            }
        ]

        call = FakeToolCall(json.dumps({"items": raw_items}))
        seen_hashes = set()
        stored = []

        result, added = parse_record_instances(
            call,
            VerifiedCityTarget,
            seen_hashes,
            stored,
            source_text=None,  # No source text
        )

        # Should accept (standard validation used, no quote validation)
        assert result["accepted"] == 1
        assert result["status"] == "ok"

    def test_parse_preserves_existing_misc_data(self):
        """Test that existing misc data is preserved when adding proofs."""
        source_text = "Target: 80% by 2030"

        raw_items = [
            {
                "description": "Target",
                "targetYear": {
                    "value": "2030",
                    "quote": "2030",
                    "confidence": 0.95,
                },
                "targetValue": {
                    "value": "80",
                    "quote": "80%",
                    "confidence": 0.95,
                },
                "status": {
                    "value": "Set",
                    "quote": "Target:",
                    "confidence": 0.8,
                },
                "misc": {
                    "custom_data": "custom_value",
                    "priority": "high",
                },
            }
        ]

        call = FakeToolCall(json.dumps({"items": raw_items}))
        seen_hashes = set()
        stored = []

        result, added = parse_record_instances(
            call,
            VerifiedCityTarget,
            seen_hashes,
            stored,
            source_text=source_text,
        )

        assert result["accepted"] == 1
        record = stored[0]

        # Check existing misc data preserved
        assert record["misc"]["custom_data"] == "custom_value"
        assert record["misc"]["priority"] == "high"

        # Check proofs added
        assert "targetYear_proof" in record["misc"]
        assert "targetValue_proof" in record["misc"]

    def test_parse_duplicate_detection_with_verified_fields(self):
        """Test that duplicate detection works with verified fields."""
        source_text = "Target: 80% by 2030"

        raw_items = [
            {
                "description": "Emission reduction target",
                "targetYear": {
                    "value": "2030",
                    "quote": "2030",
                    "confidence": 0.95,
                },
                "targetValue": {
                    "value": "80",
                    "quote": "80%",
                    "confidence": 0.95,
                },
                "status": {
                    "value": "Set",
                    "quote": "Target:",
                    "confidence": 0.8,
                },
            },
            {
                "description": "Emission reduction target",
                "targetYear": {
                    "value": "2030",
                    "quote": "2030",
                    "confidence": 0.95,
                },
                "targetValue": {
                    "value": "80",
                    "quote": "80%",
                    "confidence": 0.95,
                },
                "status": {
                    "value": "Set",
                    "quote": "Target:",
                    "confidence": 0.8,
                },
            },
        ]

        call = FakeToolCall(json.dumps({"items": raw_items}))
        seen_hashes = set()
        stored = []

        result, added = parse_record_instances(
            call,
            VerifiedCityTarget,
            seen_hashes,
            stored,
            source_text=source_text,
        )

        # Should accept 1 and detect duplicate
        assert result["accepted"] == 1
        assert len(result["errors"]) == 1
        assert "duplicate" in result["errors"][0].lower()
        assert len(stored) == 1
