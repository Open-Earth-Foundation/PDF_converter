"""Unit tests for VerifiedField validation."""

import pytest
from pydantic import ValidationError

from extraction.utils.verified_field import VerifiedField


class TestVerifiedFieldValidation:
    """Test VerifiedField validators."""

    def test_valid_verified_field(self):
        """Test creating a valid VerifiedField."""
        field = VerifiedField[str](
            value="2030",
            quote="by 2030",
            confidence=0.95,
        )
        assert field.value == "2030"
        assert field.quote == "by 2030"
        assert field.confidence == 0.95

    def test_verified_field_with_none_value(self):
        """Test VerifiedField with None value but valid quote."""
        field = VerifiedField[int](
            value=None,
            quote="no baseline specified",
            confidence=0.9,
        )
        assert field.value is None
        assert field.quote == "no baseline specified"
        assert field.confidence == 0.9

    def test_empty_quote_rejected(self):
        """Test that empty quote is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            VerifiedField[str](
                value="2030",
                quote="",
                confidence=0.95,
            )
        assert "quote" in str(exc_info.value).lower()

    def test_whitespace_only_quote_rejected(self):
        """Test that whitespace-only quote is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            VerifiedField[str](
                value="2030",
                quote="   ",
                confidence=0.95,
            )
        assert "quote" in str(exc_info.value).lower()

    def test_confidence_too_high_rejected(self):
        """Test that confidence > 1.0 is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            VerifiedField[str](
                value="2030",
                quote="by 2030",
                confidence=1.5,
            )
        assert "confidence" in str(exc_info.value).lower()

    def test_confidence_too_low_rejected(self):
        """Test that confidence < 0.0 is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            VerifiedField[str](
                value="2030",
                quote="by 2030",
                confidence=-0.1,
            )
        assert "confidence" in str(exc_info.value).lower()

    def test_confidence_exactly_zero(self):
        """Test that confidence exactly 0.0 is accepted."""
        field = VerifiedField[str](
            value=None,
            quote="unknown",
            confidence=0.0,
        )
        assert field.confidence == 0.0

    def test_confidence_exactly_one(self):
        """Test that confidence exactly 1.0 is accepted."""
        field = VerifiedField[str](
            value="2030",
            quote="by 2030",
            confidence=1.0,
        )
        assert field.confidence == 1.0

    def test_integer_confidence_accepted(self):
        """Test that integer confidence values are converted to float."""
        field = VerifiedField[str](
            value="2030",
            quote="by 2030",
            confidence=1,  # integer
        )
        assert field.confidence == 1.0
        assert isinstance(field.confidence, float)

    def test_non_string_confidence_rejected(self):
        """Test that non-numeric confidence is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            VerifiedField[str](
                value="2030",
                quote="by 2030",
                confidence="high",  # type: ignore
            )
        assert "confidence" in str(exc_info.value).lower()

    def test_verified_field_generic_types(self):
        """Test VerifiedField with different value types."""
        # String
        field_str = VerifiedField[str](
            value="test",
            quote="test",
            confidence=0.9,
        )
        assert field_str.value == "test"

        # Integer
        field_int = VerifiedField[int](
            value=100,
            quote="100",
            confidence=0.95,
        )
        assert field_int.value == 100

        # Float
        field_float = VerifiedField[float](
            value=3.14,
            quote="3.14",
            confidence=0.9,
        )
        assert field_float.value == 3.14
