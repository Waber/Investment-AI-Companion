"""One checker for text a person typed.

Company names, watchlist labels, note bodies, and thesis fields all
call ``clean_text``. The rules stay here so a form and the API cannot
drift apart. The ``/ui`` forms still have their own copy until the
Frontend Developer switches them over. They should import this module
and the length constants (``COMPANY_NAME_MAX``, ``NOTE_BODY_MAX``, and
the others), not grow a third copy of the checks.

The checks run in a fixed order. A later check must not hide an
earlier one:

1. On the raw text, before ``strip``:

   - a surrogate (Unicode category ``Cs``, for example ``\\ud800``)
     is ``surrogate``
   - a bidi or other hidden format control is ``bidi``
   - a control character (category ``Cc``) is ``control_char``

   ``allow_newlines=True`` (a note body, a thesis body, or thesis
   breakers) still allows ``\\n``, ``\\r``, and ``\\t``. Every other
   ``Cc`` character is rejected. ``allow_newlines=False`` rejects
   those three as well. ``"ETF\\n"`` is therefore ``control_char``,
   not the word ETF with the newline stripped off.

2. ``str.strip`` removes whitespace at the ends only. A zero-width
   character at the edge is not whitespace, so it stays.

3. Blank check. The value is blank when nothing is left, or when
   every remaining character is whitespace or category ``Cf``
   (format), ``Co`` (private use), or ``Cn`` (unassigned). ``Cf``
   is included because a value made only of invisible characters
   such as U+200B or U+FEFF is not a name or a note. ``Co`` and
   ``Cn`` are the same kind of filler. A ``Cf``, ``Co``, or ``Cn``
   character next to a letter is kept, including at an edge. This
   step does not strip those characters out of real text.

4. ``max_len`` is the length of the stripped text. Padding spaces
   do not count. A blank value fails step 3, so it is never
   ``too_long``.

``allow_blank=True`` turns a blank value into ``None``. That is the
empty convention for the whole helper. The watchlist stores that
``None`` as SQL NULL. Thesis-breakers are a non-null column, so
their model turns this ``None`` into ``""`` after the call. Callers
must not invent a second empty string.

``TextValidationError`` is a ``ValueError``. Its message is safe to
put in an API response: it names the field and the problem, and it
does not repeat the text that failed. Pydantic still attaches the
original input to the 422 body. That field is the existing error
shape, not this message.
"""

import unicodedata
from typing import Literal, overload

# Closed set. A new failure needs a new code and a test, not a
# free-form sentence.
TEXT_VALIDATION_CODES = (
    "blank",
    "too_long",
    "control_char",
    "bidi",
    "surrogate",
)

# Bidi overrides U+202A–U+202E, isolates U+2066–U+2069, and the
# marks U+200E LRM, U+200F RLM, and U+061C ALM. They reorder the
# letters around them. The same code also covers the hidden format
# characters from issue #86: deprecated controls U+206A–U+206F and
# tag characters U+E0000–U+E007F. Those can hide text inside a
# prompt. The agreed code list has no sixth value, so they share
# ``bidi`` and are rejected on the raw text, not stored as blank.
_BIDI_AND_HIDDEN = frozenset(
    chr(codepoint)
    for codepoint in (
        *range(0x202A, 0x202F),
        *range(0x2066, 0x206A),
        0x200E,
        0x200F,
        0x061C,
        *range(0x206A, 0x2070),
        *range(0xE0000, 0xE0080),
    )
)

# Category Cc characters a multi-line field may contain. Any other
# Cc character, including NUL, DEL, and NEL (U+0085), is
# ``control_char``. NEL is a line break for ``str.splitlines``.
# Allowing it in a note would let one field forge a second log line.
# ``strip`` on master removed a NEL at the edge. It is rejected now.
_NEWLINE_CONTROLS = frozenset("\n\r\t")

# A value made only of these, plus whitespace, is blank. ``Cs`` is
# not here: a surrogate already failed step 1. Bidi format
# characters are ``Cf`` too, and they also failed step 1.
_BLANK_CATEGORIES = frozenset({"Cf", "Co", "Cn"})


class TextValidationError(ValueError):
    """One text check failed.

    ``code`` is one of ``TEXT_VALIDATION_CODES``. ``field`` is the
    name the caller passed (``name``, ``label``, ``body``, ...).
    ``str(error)`` is the sentence the API shows.

    ``message`` replaces that sentence. It is a fixed string: it
    must not contain the text that failed. The company name uses
    it so a blank name still says ``name must contain a visible
    character``, which is the sentence the API showed before this
    helper. The code and the field stay on the exception, so the
    422 body can still name them.
    """

    def __init__(
        self,
        code: str,
        field: str,
        max_len: int | None = None,
        *,
        message: str | None = None,
    ):
        self.code = code
        self.field = field
        if message is None:
            message = _message(code, field, max_len)
        super().__init__(message)


def _message(code: str, field: str, max_len: int | None) -> str:
    """Build a sentence that does not contain the rejected text."""
    if code == "blank":
        return field + " must not be blank"
    if code == "too_long":
        return field + " must be at most " + str(max_len) + " characters"
    if code == "control_char":
        return field + " must not contain control characters"
    if code == "bidi":
        return field + " must not contain hidden or bidi controls"
    if code == "surrogate":
        return field + " must not contain unpaired surrogates"
    return field + " is not valid text"


def _is_blank(value: str) -> bool:
    """True when ``value`` has no visible character.

    The caller already stripped the ends. A space between two
    zero-width characters is still here, and it is still blank.
    """
    if value == "":
        return True
    for char in value:
        if char.isspace():
            continue
        if unicodedata.category(char) in _BLANK_CATEGORIES:
            continue
        return False
    return True


@overload
def clean_text(
    value: str | None,
    *,
    field: str,
    max_len: int,
    allow_newlines: bool = False,
    allow_blank: Literal[False] = False,
) -> str: ...


@overload
def clean_text(
    value: str | None,
    *,
    field: str,
    max_len: int,
    allow_newlines: bool = False,
    allow_blank: Literal[True],
) -> str | None: ...


def clean_text(
    value: str | None,
    *,
    field: str,
    max_len: int,
    allow_newlines: bool = False,
    allow_blank: bool = False,
) -> str | None:
    """Validate and strip one text field.

    See the module docstring for the order. ``None`` with
    ``allow_blank=True`` is the empty convention (``None``). ``None``
    with ``allow_blank=False`` is ``blank``. Any other non-string is
    a programming error: the caller should leave it for Pydantic's
    type check instead of passing it here.

    A successful call returns the stripped string. A blank value
    with ``allow_blank=True`` returns ``None``, not ``""``.
    """
    if value is None:
        if allow_blank:
            return None
        raise TextValidationError("blank", field)
    if not isinstance(value, str):
        raise TypeError("clean_text expects str or None")

    # Three walks, not one. The first bad character in the string
    # must not win when a higher-priority check fails later on.
    # ``"\\n\\ud800"`` is a surrogate, not a control character.
    for char in value:
        if unicodedata.category(char) == "Cs":
            raise TextValidationError("surrogate", field)
    for char in value:
        if char in _BIDI_AND_HIDDEN:
            raise TextValidationError("bidi", field)
    for char in value:
        if unicodedata.category(char) != "Cc":
            continue
        if allow_newlines and char in _NEWLINE_CONTROLS:
            continue
        raise TextValidationError("control_char", field)

    stripped = value.strip()
    if _is_blank(stripped):
        if allow_blank:
            return None
        raise TextValidationError("blank", field)
    if len(stripped) > max_len:
        raise TextValidationError("too_long", field, max_len)
    return stripped
