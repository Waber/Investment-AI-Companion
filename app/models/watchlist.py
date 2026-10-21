"""Watchlist read and write models.

One list in v1. A row points at a company. The optional label is a
short note, not a second name. The read model does not apply the
write-time length check, so a longer label already stored can still
be listed.
"""

import unicodedata
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

# The column is String(80). The write model uses the same limit so a
# too-long note is HTTP 422 instead of a database error on PostgreSQL.
WATCHLIST_LABEL_MAX_LENGTH = 80

# Bidi overrides, embeddings, isolates, and the left/right marks.
# U+200E and U+200F are format characters (Cf). They are rejected
# here instead of being treated as blank. The company-name helper
# is a separate rule and is not used for a watchlist label.
_BIDI_CONTROLS = frozenset(
    chr(codepoint)
    for codepoint in (
        *range(0x202A, 0x202F),
        *range(0x2066, 0x206A),
        0x200E,
        0x200F,
    )
)


def clean_watchlist_label(value: object) -> object:
    """Strip a label. A blank label is stored as null.

    ``None`` and non-strings are left alone. The field type rejects a
    non-string.

    After stripping, a control character (Unicode category Cc, which
    includes NUL) or a bidi control is a validation error. A label
    made only of whitespace or format characters (category Cf, such
    as U+200B and U+FEFF) is the same as omitting the note, so it
    becomes null. A format character next to a letter is kept.
    """
    if value is None or not isinstance(value, str):
        return value
    stripped = value.strip()
    if any(unicodedata.category(char) == "Cc" for char in stripped):
        raise ValueError("label must not contain control characters")
    if any(char in _BIDI_CONTROLS for char in stripped):
        raise ValueError("label must not contain bidi controls")
    if stripped and any(
        unicodedata.category(char) != "Cf" for char in stripped
    ):
        return stripped
    return None


class WatchlistItemCreate(BaseModel):
    """Input for adding a company to the watchlist."""

    company_id: int = Field(..., gt=0, description="Company to track")
    label: Optional[str] = Field(
        None,
        max_length=WATCHLIST_LABEL_MAX_LENGTH,
        description="Optional short note",
    )

    @field_validator("label", mode="before")
    @classmethod
    def _clean_label(cls, value: object) -> object:
        return clean_watchlist_label(value)


class WatchlistItem(BaseModel):
    """One stored watchlist row."""

    id: int
    company_id: int
    added_at: datetime
    label: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)
