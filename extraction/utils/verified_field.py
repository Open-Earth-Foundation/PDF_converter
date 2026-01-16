"""VerifiedField type for Evidence Pattern enforcement in extraction."""

from __future__ import annotations

from typing import Generic, TypeVar, Union, Optional
from pydantic import BaseModel, Field, field_validator

T = TypeVar("T")


class VerifiedField(BaseModel, Generic[T]):
    """
    A generic field type that wraps a value with proof of evidence.

    Used during extraction to ensure every numeric/date/status value is backed by
    an exact quote and confidence score from the source document.

    Attributes:
        value: The extracted value (can be None if not present in source).
        quote: Verbatim quote from the source document (must be non-empty).
        confidence: Confidence score for the extraction (0.0 to 1.0).

    Example:
        VerifiedField[str](
            value="2030",
            quote="by 2030",
            confidence=0.95
        )

    Example with None value:
        VerifiedField[int](
            value=None,
            quote="no baseline specified",
            confidence=0.9
        )
    """

    value: Union[T, None] = Field(description="The extracted value (None if not present)")
    quote: str = Field(description="Verbatim quote from source document")
    confidence: float = Field(description="Confidence score (0.0 to 1.0)")

    @field_validator("quote")
    @classmethod
    def quote_must_be_nonempty(cls, v: str) -> str:
        """Ensure quote is a non-empty string."""
        if not isinstance(v, str) or not v.strip():
            raise ValueError("quote must be a non-empty string")
        return v

    @field_validator("confidence")
    @classmethod
    def confidence_in_range(cls, v: float) -> float:
        """Ensure confidence is between 0.0 and 1.0."""
        if not isinstance(v, (int, float)):
            raise ValueError("confidence must be a number")
        if not (0.0 <= v <= 1.0):
            raise ValueError(f"confidence must be between 0.0 and 1.0, got {v}")
        return float(v)
