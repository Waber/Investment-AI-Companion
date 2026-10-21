"""Notes and investment theses attached to one company.

The UI imports the constants, ``ThesisStatus``, and the Pydantic
models from this module. The SQLAlchemy tables live in
``app.models.database_models``. The repositories return these
models, not the table rows.

``NoteCreate``, ``NoteUpdate``, ``ThesisCreate``, and
``ThesisUpdate`` are the only models that normalize text. A write
strips leading and trailing whitespace, then checks the length.
Padding spaces do not count toward the maximum. A title or a body
that is empty after stripping is rejected. So is one made only of
invisible format characters (Unicode category Cf, such as U+200B
or U+FEFF) and whitespace, including a space that sits between
those characters. Thesis-breakers may be empty: a new thesis does
not have to list any yet, and a breakers value that is only
whitespace or format characters is stored as ``""``. A letter
with a format character beside it is kept.

A title also strips format characters at the edges, rejects bidi
controls, and rejects line and paragraph separators. A multi-line
field turns ``\\r\\n`` and a lone ``\\r`` into ``\\n`` before the
length check, so a Windows newline counts as one character.

``Note`` and ``Thesis`` are output models. They do not run those
checks again. A row that was stored before a rule existed, or
written past the repository, can still be listed. Re-checking it
here would turn one bad row into an error for the whole list.

Unicode category Cc is a control character (for example NUL, DEL,
and the C1 controls). A title is one line, so every Cc character
is rejected. A body and the thesis-breakers allow newline and tab
after the carriage-return normalization, and reject every other
Cc character. Failures on a write model are Pydantic's
``ValidationError``. The UI maps that exception to HTTP 422.
"""

import unicodedata
from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator

# Stored as VARCHAR of this length. PostgreSQL enforces it. The
# Pydantic models enforce it on SQLite as well, after stripping.
NOTE_BODY_MAX = 10000
THESIS_TITLE_MAX = 200
THESIS_BODY_MAX = 10000
THESIS_BREAKERS_MAX = 5000

# After ``\\r`` has been turned into ``\\n``, these are the only
# control characters a multi-line field may still contain. They
# are category Cc, so the check below has to allow them by hand.
_MULTILINE_CONTROLS = frozenset("\n\t")

# Bidi overrides, isolates, and marks reorder the letters around
# them. They are format characters, so an edge-strip would hide
# one that sits at the start or end of a title. The title rejects
# them anywhere in the original text instead.
# U+202A–U+202E overrides, U+2066–U+2069 isolates,
# U+200E LRM, U+200F RLM, U+061C Arabic letter mark.
_BIDI_CONTROLS = frozenset(
    chr(codepoint)
    for codepoint in (
        *range(0x202A, 0x202F),
        *range(0x2066, 0x206A),
        0x200E,
        0x200F,
        0x061C,
    )
)

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


def _only_format_characters(value: str) -> bool:
    """True when nothing visible is left among format characters.

    Cf is an invisible format character: zero-width space (U+200B),
    the byte-order mark (U+FEFF), and the joiners U+200C and U+200D.
    ``str.strip`` only drops whitespace at the ends, so a normal
    space between two of those characters is still in ``value``.
    That space is not visible either. The value is blank when every
    character is whitespace or category Cf. A letter with a format
    character beside it is not blank.
    """
    return value != "" and all(
        char.isspace() or unicodedata.category(char) == "Cf" for char in value
    )


def _is_title_edge(char: str) -> bool:
    """True for whitespace or a format character at a title's edge.

    ``str.strip`` removes whitespace only. A zero-width space before
    the first letter would otherwise stay in the stored title.
    """
    return char.isspace() or unicodedata.category(char) == "Cf"


def _strip_title_edges(value: str) -> str:
    """Remove whitespace and Cf characters from both ends.

    The two loops keep going so a space that was hidden behind a
    format character is removed too. A format character between
    letters is not at an edge, so it stays.
    """
    start = 0
    end = len(value)
    while start < end and _is_title_edge(value[start]):
        start += 1
    while end > start and _is_title_edge(value[end - 1]):
        end -= 1
    return value[start:end]


def _reject_blank(value: str, *, allow_blank: bool, field_name: str) -> str:
    """Return ``value``, or ``""`` when a blank value is allowed."""
    if value == "" or _only_format_characters(value):
        if allow_blank:
            return ""
        raise ValueError(field_name + " must not be blank")
    return value


def _normalize_title(value: str, *, allow_blank: bool, field_name: str) -> str:
    """Normalize one title the way ``normalize_name`` treats a name.

    Bidi controls and line or paragraph separators (categories Zl
    and Zp, U+2028 and U+2029) are rejected on the original text.
    An edge-strip would otherwise delete a mark that sits at either
    end and store the rest. Format characters at the edges are then
    removed. A letter with one beside it is kept. A control
    character that remains is rejected. The length limit runs after
    this function returns.
    """
    if any(char in _BIDI_CONTROLS for char in value):
        raise ValueError(field_name + " must not contain bidi controls")
    if any(unicodedata.category(char) in {"Zl", "Zp"} for char in value):
        raise ValueError(
            field_name + " must not contain line or paragraph separators"
        )
    stripped = _reject_blank(
        _strip_title_edges(value),
        allow_blank=allow_blank,
        field_name=field_name,
    )
    for char in stripped:
        if unicodedata.category(char) == "Cc":
            raise ValueError(
                field_name + " must not contain control characters"
            )
    return stripped


def _normalize_multiline(
    value: str,
    *,
    allow_blank: bool,
    field_name: str,
) -> str:
    """Strip ends, fold newlines, then reject a blank value.

    ``\\r\\n`` and a lone ``\\r`` become ``\\n`` before the length
    check. The field's ``max_length`` sees this string, so a body
    of CR LF pairs is measured in newlines, not in pairs. ``strip``
    still removes a newline at either end. NUL and the other
    control characters are rejected. Newline and tab are kept.
    """
    stripped = value.strip().replace("\r\n", "\n").replace("\r", "\n")
    normalized = _reject_blank(
        stripped,
        allow_blank=allow_blank,
        field_name=field_name,
    )
    for char in normalized:
        if unicodedata.category(char) != "Cc":
            continue
        if char in _MULTILINE_CONTROLS:
            continue
        raise ValueError(field_name + " must not contain control characters")
    return normalized


def normalize_research_text(
    value: object,
    *,
    allow_blank: bool,
    allow_multiline: bool,
    field_name: str,
) -> object:
    """Normalize one write-model field.

    ``None`` and non-strings are returned unchanged so Pydantic can
    report the type error. ``allow_multiline`` is false for a title
    and true for a body or thesis-breakers. Read models do not call
    this function.
    """
    if not isinstance(value, str):
        return value
    if allow_multiline:
        return _normalize_multiline(
            value,
            allow_blank=allow_blank,
            field_name=field_name,
        )
    return _normalize_title(
        value,
        allow_blank=allow_blank,
        field_name=field_name,
    )


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

    model_config = _WRITE_MODEL_CONFIG

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

    model_config = _WRITE_MODEL_CONFIG

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
    """One stored thesis, including status and timestamps.

    This is an output model. Title, body, and thesis-breakers are
    returned as stored. They are not stripped and they are not
    checked against the write-model length limits.
    """

    id: int
    company_id: int
    title: str
    body: str
    thesis_breakers: str
    status: ThesisStatus
    created_at: datetime
    updated_at: datetime

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
