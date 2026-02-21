"""Validation logic for editable fields."""

from __future__ import annotations

import re
from datetime import date
from typing import Optional, Tuple

from utils.helpers import normalize_text, parse_date

MIN_ALLOWED_DATE = date(2022, 1, 1)
STRICT_ISO_DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def validate_optional_date(value: object, field_name: str, strict_iso: bool = False) -> Tuple[bool, str, str]:
    """Validate optional YYYY-MM-DD dates that must not be in the future."""
    raw_value = normalize_text(value)
    if not raw_value:
        return True, "", ""

    if strict_iso and not STRICT_ISO_DATE_PATTERN.fullmatch(raw_value):
        return False, f"{field_name} must be in YYYY-MM-DD format.", ""

    parsed_value: Optional[date] = parse_date(value)
    if parsed_value is None:
        if strict_iso:
            return False, f"{field_name} must be a valid date in YYYY-MM-DD format.", ""
        return False, f"{field_name} must be a valid date (YYYY-MM-DD, YYYY-MM, or YYYY).", ""

    if parsed_value < MIN_ALLOWED_DATE:
        return False, f"{field_name} cannot be before {MIN_ALLOWED_DATE.isoformat()}.", ""

    if parsed_value > date.today():
        return False, f"{field_name} cannot be in the future.", ""

    return True, "", parsed_value.isoformat()


def validate_comment(value: object) -> Tuple[bool, str, str]:
    """Validate and normalize comment text."""
    return True, "", normalize_text(value)


def validate_edit_payload(
    review_date: object,
    layer_date: object,
    test_date: object,
    comment: object,
) -> Tuple[bool, Optional[str], dict]:
    """Validate an edit payload and return normalized values."""
    review_valid, review_error, review_value = validate_optional_date(review_date, "review_date")
    if not review_valid:
        return False, review_error, {}

    layer_valid, layer_error, layer_value = validate_optional_date(layer_date, "layer_date")
    if not layer_valid:
        return False, layer_error, {}

    test_valid, test_error, test_value = validate_optional_date(
        test_date,
        "test_date",
        strict_iso=True,
    )
    if not test_valid:
        return False, test_error, {}

    comment_valid, comment_error, comment_value = validate_comment(comment)
    if not comment_valid:
        return False, comment_error, {}

    normalized = {
        "review_date": review_value,
        "layer_date": layer_value,
        "test_date": test_value,
        "comment": comment_value,
    }
    return True, None, normalized
