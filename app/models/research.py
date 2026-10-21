"""Notes and investment theses attached to one company.

The UI imports the constants, ``ThesisStatus``, and the Pydantic
models from this module. The SQLAlchemy tables live in
``app.models.database_models``. The repositories return these
models, not the table rows.

A write strips leading and trailing whitespace, then checks the
length. Padding spaces do not count toward the maximum. A title
or a body that is empty after stripping is rejected. Thesis-breakers
may be empty: a new thesis does not have to list any yet.

Unicode category Cc is a control character (for example NUL, DEL,
and the C1 controls). A title is one line, so every Cc character
is rejected. A body and the thesis-breakers are multi-line, so
newline, carriage return, and tab are kept and every other Cc
character is rejected. Failures are Pydantic's ``ValidationError``.
The UI maps that exception to HTTP 422.
"""

import unicodedata
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator

# Stored as VARCHAR of this length. PostgreSQL enforces it. The
# Pydantic models enforce it on SQLite as well, after stripping.
NOTE_BODY_MAX = 10000
THESIS_TITLE_MAX = 200
THESIS_BODY_MAX = 10000
THESIS_BREAKERS_MAX = 5000

# Newline, carriage return, and tab are the only control characters
# a multi-line field may contain. They are category Cc, so the
# check below has to allow them by hand.
_MULTILINE_CONTROLS = frozenset("\n\r\t")


class ThesisStatus(str, Enum):
    """Whether an investment thesis is still being used.

    ``active`` is the default for a new thesis. ``closed`` means the
    idea is kept for the record and is no longer the current view.
    The values are stored in lowercase. ``ACTIVE`` is not a status.
    """

    ACTIVE = "active"
    CLOSED = "closed"


THESIS_STATUS_CHECK = "status IN ({})".format(
    ", ".join("'{}'".format(item.value) for item in ThesisStatus)
)


def normalize_research_text(
    value: object,
    *,
    allow_blank: bool,
    allow_multiline: bool,
    field_name: str,
) -> object:
    """Strip ends, then reject a blank value and control characters.

    ``None`` and non-strings are returned unchanged so Pydantic can
    report the type error. ``str.strip`` removes Unicode whitespace,
    which includes a newline at either end. A newline that sits in
    the middle of a title is still a control character and is
    rejected. The length limit is applied by the field after this
    function returns, so it sees the stripped text.
    """
    if not isinstance(value, str):
        return value
    stripped = value.strip()
    if stripped == "" and not allow_blank:
        raise ValueError(field_name + " must not be blank")
    for char in stripped:
        if unicodedata.category(char) != "Cc":
            continue
        if allow_multiline and char in _MULTILINE_CONTROLS:
            continue
        raise ValueError(field_name + " must not contain control characters")
    return stripped


def _optional_text(
    value: object,
    field_name: str,
    *,
    allow_blank: bool,
    allow_multiline: bool,
) -> object:
    """Normalize one field on an update model.

    Omitting the field never calls this function, so the stored
    value stays. A JSON null does call it. Null is rejected: the
    column is not nullable, and a null must not wipe the text.
    """
    if value is None:
        raise ValueError(
            field_name + " cannot be null; omit it to keep the stored value"
        )
    return normalize_research_text(
        value,
        allow_blank=allow_blank,
        allow_multiline=allow_multiline,
        field_name=field_name,
    )


class NoteCreate(BaseModel):
    """Body of a new note. The company id is a repository argument."""

    body: str = Field(..., max_length=NOTE_BODY_MAX)

    @field_validator("body", mode="before")
    @classmethod
    def _body(cls, value: object) -> object:
        return normalize_research_text(
            value,
            allow_blank=False,
            allow_multiline=True,
            field_name="body",
        )


class NoteUpdate(BaseModel):
    """Partial edit of a note. The only field is optional."""

    body: str | None = Field(default=None, max_length=NOTE_BODY_MAX)

    @field_validator("body", mode="before")
    @classmethod
    def _body(cls, value: object) -> object:
        return _optional_text(
            value,
            "body",
            allow_blank=False,
            allow_multiline=True,
        )


class Note(BaseModel):
    """One stored note, including the database id and timestamps."""

    id: int
    company_id: int
    body: str = Field(..., max_length=NOTE_BODY_MAX)
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @field_validator("body", mode="before")
    @classmethod
    def _body(cls, value: object) -> object:
        return normalize_research_text(
            value,
            allow_blank=False,
            allow_multiline=True,
            field_name="body",
        )


class ThesisCreate(BaseModel):
    """A new thesis. Status defaults to active. Breakers may be empty."""

    title: str = Field(..., max_length=THESIS_TITLE_MAX)
    body: str = Field(..., max_length=THESIS_BODY_MAX)
    thesis_breakers: str = Field(default="", max_length=THESIS_BREAKERS_MAX)
    status: ThesisStatus = ThesisStatus.ACTIVE

    @field_validator("title", mode="before")
    @classmethod
    def _title(cls, value: object) -> object:
        return normalize_research_text(
            value,
            allow_blank=False,
            allow_multiline=False,
            field_name="title",
        )

    @field_validator("body", mode="before")
    @classmethod
    def _body(cls, value: object) -> object:
        return normalize_research_text(
            value,
            allow_blank=False,
            allow_multiline=True,
            field_name="body",
        )

    @field_validator("thesis_breakers", mode="before")
    @classmethod
    def _thesis_breakers(cls, value: object) -> object:
        return normalize_research_text(
            value,
            allow_blank=True,
            allow_multiline=True,
            field_name="thesis_breakers",
        )


class ThesisUpdate(BaseModel):
    """Partial edit of a thesis. Every field is optional.

    ``status`` may be sent here. ``ThesisRepository.set_status`` is
    the other way to close or reopen a thesis without editing text.
    """

    title: str | None = Field(default=None, max_length=THESIS_TITLE_MAX)
    body: str | None = Field(default=None, max_length=THESIS_BODY_MAX)
    thesis_breakers: str | None = Field(
        default=None,
        max_length=THESIS_BREAKERS_MAX,
    )
    status: ThesisStatus | None = None

    @field_validator("title", mode="before")
    @classmethod
    def _title(cls, value: object) -> object:
        return _optional_text(
            value,
            "title",
            allow_blank=False,
            allow_multiline=False,
        )

    @field_validator("body", mode="before")
    @classmethod
    def _body(cls, value: object) -> object:
        return _optional_text(
            value,
            "body",
            allow_blank=False,
            allow_multiline=True,
        )

    @field_validator("thesis_breakers", mode="before")
    @classmethod
    def _thesis_breakers(cls, value: object) -> object:
        return _optional_text(
            value,
            "thesis_breakers",
            allow_blank=True,
            allow_multiline=True,
        )

    @field_validator("status", mode="before")
    @classmethod
    def _status(cls, value: object) -> object:
        if value is None:
            raise ValueError(
                "status cannot be null; omit it to keep the stored status"
            )
        return value


class Thesis(BaseModel):
    """One stored thesis, including status and timestamps."""

    id: int
    company_id: int
    title: str = Field(..., max_length=THESIS_TITLE_MAX)
    body: str = Field(..., max_length=THESIS_BODY_MAX)
    thesis_breakers: str = Field(..., max_length=THESIS_BREAKERS_MAX)
    status: ThesisStatus
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @field_validator("title", mode="before")
    @classmethod
    def _title(cls, value: object) -> object:
        return normalize_research_text(
            value,
            allow_blank=False,
            allow_multiline=False,
            field_name="title",
        )

    @field_validator("body", mode="before")
    @classmethod
    def _body(cls, value: object) -> object:
        return normalize_research_text(
            value,
            allow_blank=False,
            allow_multiline=True,
            field_name="body",
        )

    @field_validator("thesis_breakers", mode="before")
    @classmethod
    def _thesis_breakers(cls, value: object) -> object:
        return normalize_research_text(
            value,
            allow_blank=True,
            allow_multiline=True,
            field_name="thesis_breakers",
        )


__all__ = [
    "NOTE_BODY_MAX",
    "THESIS_BODY_MAX",
    "THESIS_BREAKERS_MAX",
    "THESIS_STATUS_CHECK",
    "THESIS_TITLE_MAX",
    "Note",
    "NoteCreate",
    "NoteUpdate",
    "Thesis",
    "ThesisCreate",
    "ThesisStatus",
    "ThesisUpdate",
]
