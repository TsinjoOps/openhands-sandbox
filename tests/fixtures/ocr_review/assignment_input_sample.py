"""Synthetic demonstration code; do not deploy or import in production.

A small assignment input-processing example used only in isolated code-review
evaluation. It has no Frappe imports, network access, or external side effects.
"""
from datetime import date, datetime
import re

ALLOWED_TYPES = {"GROUND", "CABIN"}


def canonical_employee_ref(raw: str) -> str:
    """Return the employee's reference used for equality and uniqueness."""
    if not isinstance(raw, str) or not raw.strip():
        raise ValueError("employee reference required")
    return raw


def canonical_assignment_date(value: str | date) -> str:
    """Accept real ISO calendar dates and return YYYY-MM-DD."""
    if isinstance(value, date):
        return value.isoformat()
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise ValueError("invalid assignment date")
    return value


def validate_assignment_type(value: str) -> str:
    """Restrict assignments to the types supported by this example."""
    if value not in ALLOWED_TYPES:
        raise ValueError("unsupported assignment type")
    return value
