"""Utilities for verified field mapping and quote validation."""

from __future__ import annotations

import re
import logging
import inspect
from typing import Any, Dict, Type, get_args, get_origin
from pydantic import BaseModel

from extraction.utils.verified_field import VerifiedField

LOGGER = logging.getLogger(__name__)


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


def is_verified_field(annotation: Any) -> bool:
    """
    Check if a type annotation is or contains VerifiedField.
    
    Handles:
    - VerifiedField[T]
    - Optional[VerifiedField[T]] (i.e., VerifiedField[T] | None)

    Args:
        annotation: The type annotation to check.

    Returns:
        True if the annotation is VerifiedField[T] or Optional[VerifiedField[T]], False otherwise.
    """
    import types
    from typing import Union
    
    origin = get_origin(annotation)
    
    # Direct VerifiedField[T]
    if origin is VerifiedField or annotation is VerifiedField:
        return True

    # Pydantic generics produce specialized subclasses; accept subclasses too.
    if inspect.isclass(annotation):
        try:
            if issubclass(annotation, VerifiedField):
                return True
        except TypeError:
            pass
    
    # Optional[VerifiedField[T]] = Union[VerifiedField[T], None]
    union_types = (Union,)
    if getattr(types, "UnionType", None) is not None:
        union_types = (Union, types.UnionType)

    if origin in union_types:
        args = get_args(annotation)
        for arg in args:
            if get_origin(arg) is VerifiedField or arg is VerifiedField:
                return True
            if inspect.isclass(arg):
                try:
                    if issubclass(arg, VerifiedField):
                        return True
                except TypeError:
                    pass
        return False
    
    return False


def get_verified_fields(model_cls: Type[BaseModel]) -> Dict[str, str]:
    """
    Get all verified fields from a model class.

    Args:
        model_cls: The Pydantic model class.

    Returns:
        Dict mapping field name (Python name) to alias name.
    """
    verified = {}
    for field_name, field_info in model_cls.model_fields.items():
        if is_verified_field(field_info.annotation):
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

    Converts VerifiedField objects to scalar values, extracts proof (quote + confidence),
    and stores proof in misc field as `{field_name}_proof` entries.
    
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
    from extraction.utils.verified_coercion import get_target_type_for_field, coerce_verified_value
    
    output_dict: Dict[str, Any] = {}
    proofs: Dict[str, Dict[str, Any]] = {}
    errors: Dict[str, str] = {}

    # Resolve model name for field mapping
    model_name = db_model_cls.__name__ if db_model_cls else type(verified_obj).__name__
    if model_name.startswith("Verified"):
        model_name = model_name[len("Verified"):]

    # Get verified fields
    verified_fields = get_verified_fields(type(verified_obj))

    # Process all fields from verified object
    for field_name, field_info in type(verified_obj).model_fields.items():
        alias = field_info.alias or field_name
        value = getattr(verified_obj, field_name, None)

        # Check if this is a verified field
        if field_name in verified_fields:
            # Value should be a VerifiedField instance
            if isinstance(value, VerifiedField):
                # Validate quote in source
                if not validate_quote_in_source(value.quote, source_text):
                    errors[field_name] = (
                        f"Quote not found in source: '{value.quote}' for field {alias}"
                    )
                    LOGGER.warning(
                        "Quote validation failed for %s: '%s'",
                        alias,
                        value.quote,
                    )
                    continue

                # Get target type for this field and coerce the value
                target_type = get_target_type_for_field(model_name, alias)
                try:
                    if target_type:
                        coerced_value = coerce_verified_value(value.value, alias, target_type)
                    else:
                        # No type coercion needed, use as-is
                        coerced_value = value.value
                    
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
                    "quote": value.quote,
                    "confidence": value.confidence,
                }
            elif value is not None:
                errors[field_name] = f"Expected VerifiedField for {alias}, got {type(value)}"
        else:
            # Regular field - copy as-is
            if value is not None:
                output_dict[alias] = value

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

    return output_dict, errors
