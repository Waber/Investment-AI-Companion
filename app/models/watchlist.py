"""Watchlist read and write models.

One list in v1. A row points at a company. The optional label is a
short note, not a second name. The read model does not apply the
write-time length check, so a longer label already stored can still
be listed.

Character rules live in ``app.validation.text.clean_text``. A blank
label is ``None`` (the helper's empty convention), which the column
stores as NULL.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.validation.text import TextValidationError, clean_text

# The column is String(80). The write model uses the same limit so a
# too-long note is HTTP 422 instead of a database error on PostgreSQL.
# The /ui form can copy this number into maxlength.
WATCHLIST_LABEL_MAX_LENGTH = 80


def clean_watchlist_label(value: object) -> object:
    """Strip a label. A blank label is stored as null.

    ``None`` and non-strings are left alone. The field type rejects a
    non-string. Everything else is ``clean_text`` with newlines
    disallowed and blanks allowed. The helper returns ``None`` for a
    blank, which is the value this column stores.

    A label that is only too long is returned stripped.
    ``Field(max_length=...)`` on ``WatchlistItemCreate`` then
    reports Pydantic ``string_too_long``, the same error a long
    label produced before this helper. This function does not
    apply that limit itself. The HTTP route always goes through
    the model, so the 422 happens before the repository inserts.
    """
    if not isinstance(value, str):
        return value
    try:
        return clean_text(
            value,
            field="label",
            max_len=WATCHLIST_LABEL_MAX_LENGTH,
            allow_newlines=False,
            allow_blank=True,
        )
    except TextValidationError as exc:
        if exc.code == "too_long":
            return value.strip()
        raise


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
