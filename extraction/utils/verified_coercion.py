"""Verified extraction field type mappings and coercion logic."""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation
from datetime import date, datetime
from typing import Any, Type

# Field type mappings for verified extraction
# Maps model name -> field name -> target type
FIELD_TYPE_MAP: dict[str, dict[str, Type]] = {
    "CityTarget": {
        "targetYear": int,
        "targetValue": Decimal,
        "baselineYear": int,
        "baselineValue": Decimal,
        "status": str,
    },
    "EmissionRecord": {
        "year": int,
        "value": int,
    },
    "CityBudget": {
        "year": int,
        "totalAmount": int,
    },
    "IndicatorValue": {
        "year": int,
        "value": Decimal,
    },
    "BudgetFunding": {
        "amount": int,
    },
    "Initiative": {
        "startYear": int,
        "endYear": int,
        "totalEstimatedCost": int,
        "status": str,
    },
}


def _coerce_year_to_int(value: Any, field_name: str) -> int:
    """Coerce a year-like value to an integer year."""
    if isinstance(value, (date, datetime)):
        return value.year
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        match = re.search(r"(19|20)\d{2}", value)
        if not match:
            raise ValueError(f"No 4-digit year found in {value!r}")
        return int(match.group(0))
    raise ValueError(f"Cannot coerce {type(value)} to year int")


def _normalize_decimal_string(raw: str) -> str:
    """Extract and normalize the first numeric token for Decimal conversion."""
    match = re.search(r"-?\d+(?:[.,]\d+)?", raw)
    if not match:
        raise ValueError(f"No numeric value found in {raw!r}")
    number = match.group(0)
    if "," in number and "." in number:
        # Assume commas are thousands separators
        number = number.replace(",", "")
    elif "," in number and "." not in number:
        # Treat comma as decimal separator unless it looks like a thousands group
        parts = number.split(",")
        if len(parts[-1]) == 3:
            number = number.replace(",", "")
        else:
            number = number.replace(",", ".")
    return number


def coerce_verified_value(value: Any, field_name: str, target_type: Type) -> Any:
    """
    Coerce a verified field value to its target database type.
    
    For verified fields, the LLM provides string values (or None).
    This function converts them to the correct types for database storage.
    
    Args:
        value: The value from VerifiedField.value (typically str or None)
        field_name: The field name (for error messages)
        target_type: The target database type (date, Decimal, int, str)
        
    Returns:
        The coerced value in the correct type, or None if value is None
        
    Raises:
        ValueError: If coercion fails
    """
    if value is None:
        return None
    
    # Already correct type
    if isinstance(value, target_type):
        return value
    
    try:
        if target_type is Decimal:
            # Convert to Decimal, then return JSON-safe string form
            if isinstance(value, str):
                normalized = _normalize_decimal_string(value)
                decimal_value = Decimal(normalized)
            elif isinstance(value, (int, float, Decimal)):
                decimal_value = Decimal(str(value))
            else:
                raise ValueError(f"Cannot coerce {type(value)} to Decimal")
            return str(decimal_value)
                
        elif target_type is int:
            # Year fields normalize to a 4-digit year
            if field_name == "year" or field_name.endswith("Year"):
                return _coerce_year_to_int(value, field_name)

            # Non-year numeric fields: convert numeric string to int
            if isinstance(value, str):
                # Remove non-numeric characters except leading minus
                clean = value.lstrip("-")
                clean = "".join(c for c in clean if c.isdigit())
                if not clean:
                    raise ValueError(f"No digits found in {value}")
                result = int(clean)
                if value.lstrip()[0] == "-":
                    result = -result
                return result
            if isinstance(value, float):
                return int(value)
            return int(value)
                
        elif target_type is str:
            # Ensure string
            return str(value)
            
        else:
            # Unknown type, try direct conversion
            return target_type(value)
            
    except (ValueError, TypeError, InvalidOperation) as e:
        raise ValueError(
            f"Failed to coerce field '{field_name}' value '{value}' to {target_type.__name__}: {e}"
        )


def get_target_type_for_field(model_name: str, field_name: str) -> Type | None:
    """
    Get the target database type for a field name within a model.

    Args:
        model_name: The database model name (e.g., "CityTarget").
        field_name: The field name (alias).

    Returns:
        The target type (Decimal, int, str) or None if not a verified field.
    """
    model_map = FIELD_TYPE_MAP.get(model_name)
    if not model_map:
        return None
    return model_map.get(field_name)
