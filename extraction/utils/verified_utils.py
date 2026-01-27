"""Utilities for verified field mapping and quote validation."""

from __future__ import annotations

import re
import logging
import inspect
from typing import Any, Dict, Type, get_args, get_origin
from uuid import UUID
from pydantic import BaseModel

from extraction.utils.verified_field import VerifiedField

LOGGER = logging.getLogger(__name__)


def _convert_uuid_to_str(value: Any) -> Any:
    """
    Recursively convert UUID objects to strings for JSON serialization.

    Args:
        value: The value to convert.

    Returns:
        The value with all UUID objects converted to strings.
    """
    if isinstance(value, UUID):
        return str(value)
    elif isinstance(value, dict):
        return {k: _convert_uuid_to_str(v) for k, v in value.items()}
    elif isinstance(value, (list, tuple)):
        return [_convert_uuid_to_str(v) for v in value]
    return value


def normalize_text_for_match(text: str) -> str:
    """
    Normalize text for robust quote matching.

    Handles:
    - Collapsing whitespace (spaces, tabs, newlines to single space)
    - Case-insensitive matching (converted to lowercase)
    - De-hyphenating line breaks (e.g., "emission-\nreduction" -> "emission reduction")

    Args:
        text: The text to normalize.

    Returns:
        Normalized text for matching.
    """
    if not isinstance(text, str):
        return str(text)

    # De-hyphenate line breaks: "-\n" or "-\r\n" becomes a space
    text = re.sub(r"-[\r\n]+", " ", text)

    # Collapse all whitespace (spaces, tabs, newlines) to single space
    text = re.sub(r"\s+", " ", text)

    # Strip leading/trailing whitespace
    text = text.strip()

    # Convert to lowercase for case-insensitive matching
    text = text.lower()

    return text


def validate_quote_in_source(quote: str, source_text: str) -> bool:
    """
    Validate that a quote appears in the source text.

    Performs robust matching by normalizing both quote and source.

    Args:
        quote: The quote to search for.
        source_text: The source text to search in.

    Returns:
        True if normalized quote is found in normalized source, False otherwise.
    """
    if not isinstance(quote, str) or not quote.strip():
        return False

    if not isinstance(source_text, str) or not source_text.strip():
        return False

    normalized_quote = normalize_text_for_match(quote)
    normalized_source = normalize_text_for_match(source_text)

    return normalized_quote in normalized_source


def get_verified_fields(model_cls: Type[BaseModel]) -> Dict[str, str]:
    """
    Get all verified fields from a model class (flat structure).

    Detects fields that have corresponding _quote and _confidence fields.

    Args:
        model_cls: The Pydantic model class.

    Returns:
        Dict mapping field name (Python name) to alias name.
    """
    verified = {}
    field_names = set(model_cls.model_fields.keys())

    for field_name, field_info in model_cls.model_fields.items():
        # Skip if this is a quote or confidence field itself
        if field_name.endswith("_quote") or field_name.endswith("_confidence"):
            continue

        # Check if this field has corresponding _quote and _confidence fields
        quote_field = f"{field_name}_quote"
        confidence_field = f"{field_name}_confidence"

        if quote_field in field_names and confidence_field in field_names:
            alias = field_info.alias or field_name
            verified[field_name] = alias

    return verified


def map_verified_to_db(
    verified_obj: BaseModel,
    source_text: str,
    db_model_cls: Type[BaseModel] | None = None,
) -> tuple[Dict[str, Any], Dict[str, str]]:
    """
    Map a verified object to database format with proof in misc field.

    Extracts values and their corresponding _quote and _confidence fields,
    validates quotes against source text, and stores proof in misc field.

    Values are coerced to their target database types (date, Decimal, int, str).

    Args:
        verified_obj: The verified Pydantic object from extraction.
        source_text: The source markdown text for validation.
        db_model_cls: Optional DB model class (not used in current implementation).

    Returns:
        Tuple of (output_dict, validation_errors)
        - output_dict: DB-compatible dict with scalar values and misc proofs.
        - validation_errors: Dict of field names to error messages (empty if all valid).
    """
    from extraction.utils.verified_coercion import (
        get_target_type_for_field,
        coerce_verified_value,
    )

    output_dict: Dict[str, Any] = {}
    proofs: Dict[str, Dict[str, Any]] = {}
    errors: Dict[str, str] = {}

    # Resolve model name for field mapping
    model_name = db_model_cls.__name__ if db_model_cls else type(verified_obj).__name__
    if model_name.startswith("Verified"):
        model_name = model_name[len("Verified") :]

    # Get verified fields
    verified_fields = get_verified_fields(type(verified_obj))

    # Process all fields from verified object
    for field_name, field_info in type(verified_obj).model_fields.items():
        # Skip quote and confidence fields (they're processed with their base field)
        if field_name.endswith("_quote") or field_name.endswith("_confidence"):
            continue

        alias = field_info.alias or field_name
        value = getattr(verified_obj, field_name, None)

        # Check if this is a verified field
        if field_name in verified_fields:
            # Get the quote and confidence
            quote_field = f"{field_name}_quote"
            confidence_field = f"{field_name}_confidence"

            quote = getattr(verified_obj, quote_field, None)
            confidence = getattr(verified_obj, confidence_field, None)

            # If value is None and we don't have quote/confidence, skip
            if value is None and (quote is None or confidence is None):
                continue

            # Validate quote is present
            if not quote or not isinstance(quote, str) or not quote.strip():
                errors[field_name] = (
                    f"Missing or empty quote for verified field {alias}"
                )
                LOGGER.warning("Missing quote for verified field %s", alias)
                continue

            # Validate confidence is present and in range
            if (
                confidence is None
                or not isinstance(confidence, (int, float))
                or not (0.0 <= confidence <= 1.0)
            ):
                errors[field_name] = (
                    f"Invalid confidence for field {alias}: {confidence}"
                )
                LOGGER.warning("Invalid confidence for field %s: %s", alias, confidence)
                continue

            # Validate quote in source
            if not validate_quote_in_source(quote, source_text):
                errors[field_name] = (
                    f"Quote not found in source: '{quote}' for field {alias}"
                )
                LOGGER.warning(
                    "Quote validation failed for %s: '%s'",
                    alias,
                    quote,
                )
                continue

            # Get target type for this field and coerce the value
            target_type = get_target_type_for_field(model_name, alias)
            try:
                if target_type:
                    coerced_value = coerce_verified_value(value, alias, target_type)
                else:
                    # No type coercion needed, use as-is
                    coerced_value = value

                output_dict[alias] = coerced_value
            except ValueError as e:
                errors[field_name] = f"Value coercion failed for {alias}: {e}"
                LOGGER.warning(
                    "Value coercion failed for %s: %s",
                    alias,
                    e,
                )
                continue

            # Store proof in misc
            proofs[f"{alias}_proof"] = {
                "quote": quote,
                "confidence": confidence,
            }
        else:
            # Regular field - copy as-is, converting UUIDs to strings
            if value is not None:
                output_dict[alias] = _convert_uuid_to_str(value)

    # Merge proofs into misc
    existing_misc = output_dict.get("misc", None)
    if existing_misc is None:
        existing_misc = {}
    elif not isinstance(existing_misc, dict):
        existing_misc = {}

    # Add proofs to misc
    for proof_key, proof_value in proofs.items():
        existing_misc[proof_key] = proof_value

    # Set misc field if there are proofs
    if proofs:
        output_dict["misc"] = existing_misc

    # Convert any remaining UUIDs to strings in the final dict
    output_dict = _convert_uuid_to_str(output_dict)

    return output_dict, errors
