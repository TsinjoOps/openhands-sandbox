"""Minimal slug normalization for the POC OpenCode Producer-Glm fixture (#22).

Standard library only.
"""

import re

_NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")


def normalize_slug(value: str) -> str:
    """Normalize a string into a slug.

    Steps:
    1. trim leading/trailing whitespace;
    2. lowercase the input;
    3. replace each run of one or more non-alphanumeric characters with a single ``-``;
    4. collapse repeated separators (covered by the same regex run rule);
    5. remove leading/trailing ``-``;
    6. return ``""`` when no alphanumeric characters remain.
    """
    if not isinstance(value, str):
        raise TypeError("value must be a string")

    # 1. trim, then 2. lowercase.
    cleaned = value.strip().lower()

    # 3 & 4. each run of non-alphanumerics becomes a single '-'.
    cleaned = _NON_ALNUM_RE.sub("-", cleaned)

    # 5. strip leading/trailing '-' (also yields "" for non-alnum-only input, 6).
    return cleaned.strip("-")
