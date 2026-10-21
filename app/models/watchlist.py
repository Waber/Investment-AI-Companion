"""Watchlist read and write models.

One list in v1. A row points at a company. The optional label is a
short note, not a second name. The read model does not apply the
write-time length check, so a longer label already stored can still
be listed.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

# The column is String(80). The write model uses the same limit so a
# too-long note is HTTP 422 instead of a database error on PostgreSQL.
WATCHLIST_LABEL_MAX_LENGTH = 80


def clean_watchlist_label(value: object) -> object:
    """Strip a label. A blank label is stored as null.

    ``None`` and non-strings are left alone. The field type rejects a
    non-string. Spaces and an empty string are the same as omitting
    the note.
    """
    if value is None or not isinstance(value, str):
        return value
    stripped = value.strip()
    return stripped or None


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
