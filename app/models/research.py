"""Notes and investment theses attached to one company.

The UI imports the constants, ``ThesisStatus``, and the Pydantic
models from this module. The SQLAlchemy tables live in
``app.models.database_models``. The repositories return these
models, not the table rows. Character checks live in
``app.validation.text.clean_text``. This module only decides which
flag each field uses, and it folds Windows newlines before that call.

``NoteCreate``, ``NoteUpdate``, ``ThesisCreate``, and
``ThesisUpdate`` are the only models that normalize text. A write
strips leading and trailing whitespace, then checks the length.
Padding spaces do not count toward the maximum. A value that is
only too long is returned stripped, and ``Field(max_length=...)``
reports Pydantic ``string_too_long``. That is the error these
fields produced before the shared helper. Raising ``too_long``
here would turn it into ``value_error``. A title or a body
that is empty after stripping is rejected. So is one made only of
whitespace, combining marks (Mn, Mc, Me), and Unicode categories
Cf, Co, and Cn (zero-width characters, private use, unassigned),
including a space that sits between those characters. A letter
with one of those characters beside it is kept, including at an
edge. A mark on that letter is kept too. Thesis-breakers may be
empty: a new thesis does not have to list any yet, and a blank
breakers value is stored as ``""``. ``clean_text`` returns ``None``
for that blank. This module turns that ``None`` into ``""`` because
the column is not nullable.

A title is one line (``allow_newlines=False``). A newline in it is
``control_char``, not stripped. A body and thesis-breakers allow
newline, carriage return, and tab. This module turns ``\\r\\n`` and
a lone ``\\r`` into ``\\n`` before ``clean_text``, so a Windows
newline counts as one character. ``clean_text`` itself does not
rewrite characters. Bidi controls, tag characters, and surrogates
are rejected on every field, including bodies.

``Note`` and ``Thesis`` are output models. They do not run those
checks again. A row that was stored before a rule existed, or
written past the repository, can still be listed. Re-checking it
here would turn one bad row into an error for the whole list.

Failures on a write model are Pydantic's ``ValidationError``. The
UI maps that exception to HTTP 422. There is no HTTP route for
notes or theses yet.
"""

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.validation.text import TextValidationError, clean_text

# Stored as VARCHAR of this length. PostgreSQL enforces it. The
# Pydantic models enforce it on SQLite as well, after stripping.
NOTE_BODY_MAX = 10000
THESIS_TITLE_MAX = 200
THESIS_BODY_MAX = 10000
THESIS_BREAKERS_MAX = 5000

# Unknown keys are a client error. A typo such as ``boddy`` must
# not be ignored and then stored as a missing body.
_WRITE_MODEL_CONFIG = ConfigDict(extra="forbid")


class ThesisStatus(StrEnum):
    """Whether an investment thesis is still being used.

    ``active`` is the default for a new thesis. ``closed`` means the
    idea is kept for the record and is no longer the current view.
    The values are stored in lowercase. ``ACTIVE`` is not a status.
    This is a ``StrEnum``, so ``str(ThesisStatus.ACTIVE)`` is
    ``"active"`` and not ``"ThesisStatus.ACTIVE"``.
    """

    ACTIVE = "active"
    CLOSED = "closed"


THESIS_STATUS_CHECK = "status IN ({})".format(
    ", ".join("'{}'".format(item.value) for item in ThesisStatus)
)


def _fold_newlines(value: str) -> str:
    """Turn a Windows newline into one LF.

    ``clean_text`` does not rewrite characters. Notes and theses
    still store CR as LF so the length limit counts a line, not a
    CR LF pair. The fold runs before ``clean_text``. A title does
    not call this: a CR in a title is a control character.
    """
    return value.replace("\r\n", "\n").replace("\r", "\n")


def normalize_research_text(
    value: object,
    *,
    max_len: int,
    allow_blank: bool,
    allow_multiline: bool,
    field_name: str,
) -> object:
    """Normalize one write-model field.

    ``None`` and non-strings are returned unchanged so Pydantic can
    report the type error. ``allow_multiline`` is false for a title
    and true for a body or thesis-breakers. Read models do not call
    this function.

    ``clean_text`` returns ``None`` when a blank is allowed. This
    function turns that ``None`` into ``""`` so thesis-breakers
    stay a string. The helper's own empty convention is still
    ``None``.

    ``too_long`` is not raised out of this function. The stripped
    text is returned so the field's ``max_length`` can report
    ``string_too_long``. The length is the length after the
    newline fold, which is what the field sees.
    """
    if not isinstance(value, str):
        return value
    text = _fold_newlines(value) if allow_multiline else value
    try:
        cleaned = clean_text(
            text,
            field=field_name,
            max_len=max_len,
            allow_newlines=allow_multiline,
            allow_blank=allow_blank,
        )
    except TextValidationError as exc:
        if exc.code != "too_long":
            raise
        cleaned = text.strip()
    if allow_blank and cleaned is None:
        return ""
    return cleaned


def _optional_text(
    value: object,
    field_name: str,
    *,
    max_len: int,
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
        max_len=max_len,
        allow_blank=allow_blank,
        allow_multiline=allow_multiline,
        field_name=field_name,
    )


class NoteCreate(BaseModel):
    """Body of a new note. The company id is a repository argument."""

    model_config = _WRITE_MODEL_CONFIG

    body: str = Field(..., max_length=NOTE_BODY_MAX)

    @field_validator("body", mode="before")
    @classmethod
    def _body(cls, value: object) -> object:
        return normalize_research_text(
            value,
            max_len=NOTE_BODY_MAX,
            allow_blank=False,
            allow_multiline=True,
            field_name="body",
        )


class NoteUpdate(BaseModel):
    """Partial edit of a note. The only field is optional."""

    model_config = _WRITE_MODEL_CONFIG

    body: str | None = Field(default=None, max_length=NOTE_BODY_MAX)

    @field_validator("body", mode="before")
    @classmethod
    def _body(cls, value: object) -> object:
        return _optional_text(
            value,
            "body",
            max_len=NOTE_BODY_MAX,
            allow_blank=False,
            allow_multiline=True,
        )


class Note(BaseModel):
    """One stored note, including the database id and timestamps.

    This is an output model. It does not strip, reject control
    characters, or apply ``max_length``. Those checks belong to
    ``NoteCreate`` and ``NoteUpdate``. A stored body that would
    fail them is still returned.
    """

    id: int
    company_id: int
    body: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ThesisCreate(BaseModel):
    """A new thesis. Status defaults to active. Breakers may be empty."""

    model_config = _WRITE_MODEL_CONFIG

    title: str = Field(..., max_length=THESIS_TITLE_MAX)
    body: str = Field(..., max_length=THESIS_BODY_MAX)
    thesis_breakers: str = Field(default="", max_length=THESIS_BREAKERS_MAX)
    status: ThesisStatus = ThesisStatus.ACTIVE

    @field_validator("title", mode="before")
    @classmethod
    def _title(cls, value: object) -> object:
        return normalize_research_text(
            value,
            max_len=THESIS_TITLE_MAX,
            allow_blank=False,
            allow_multiline=False,
            field_name="title",
        )

    @field_validator("body", mode="before")
    @classmethod
    def _body(cls, value: object) -> object:
        return normalize_research_text(
            value,
            max_len=THESIS_BODY_MAX,
            allow_blank=False,
            allow_multiline=True,
            field_name="body",
        )

    @field_validator("thesis_breakers", mode="before")
    @classmethod
    def _thesis_breakers(cls, value: object) -> object:
        return normalize_research_text(
            value,
            max_len=THESIS_BREAKERS_MAX,
            allow_blank=True,
            allow_multiline=True,
            field_name="thesis_breakers",
        )


class ThesisUpdate(BaseModel):
    """Partial edit of a thesis. Every field is optional.

    ``status`` may be sent here. ``ThesisRepository.set_status`` is
    the other way to close or reopen a thesis without editing text.
    """

    model_config = _WRITE_MODEL_CONFIG

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
            max_len=THESIS_TITLE_MAX,
            allow_blank=False,
            allow_multiline=False,
        )

    @field_validator("body", mode="before")
    @classmethod
    def _body(cls, value: object) -> object:
        return _optional_text(
            value,
            "body",
            max_len=THESIS_BODY_MAX,
            allow_blank=False,
            allow_multiline=True,
        )

    @field_validator("thesis_breakers", mode="before")
    @classmethod
    def _thesis_breakers(cls, value: object) -> object:
        return _optional_text(
            value,
            "thesis_breakers",
            max_len=THESIS_BREAKERS_MAX,
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
    """One stored thesis, including status and timestamps.

    This is an output model. Title, body, and thesis-breakers are
    returned as stored. They are not stripped and they are not
    checked against the write-model length limits.

    ``closed_at`` is when the thesis was closed. It is None while the
    thesis is active. A thesis that was already closed before
    revision 0008 has the time of its last edit.
    """

    id: int
    company_id: int
    title: str
    body: str
    thesis_breakers: str
    status: ThesisStatus
    created_at: datetime
    updated_at: datetime
    closed_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


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
