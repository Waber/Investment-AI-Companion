"""The shared free-text checker.

These tests pin the order and the five codes. Model and HTTP tests
cover the same rules on each field that calls the helper.
"""

import unicodedata

import pytest

from app.validation.text import (
    TEXT_VALIDATION_CODES,
    TextValidationError,
    clean_text,
)

# Bidi overrides, isolates, and the three marks named in the contract.
_BIDI = (
    "\u202a",
    "\u202b",
    "\u202c",
    "\u202d",
    "\u202e",
    "\u2066",
    "\u2067",
    "\u2068",
    "\u2069",
    "\u200e",
    "\u200f",
    "\u061c",
)
# Deprecated format controls and one tag character from each end of
# U+E0000–U+E007F. They use the bidi code. See the helper docstring.
_HIDDEN = ("\u206a", "\u206f", "\U000e0000", "\U000e007f")

# A family emoji is seven code points: four emoji and three ZWJ
# (U+200D). max_len counts those code points, not one grapheme.
_FAMILY = "\U0001f468\u200d\U0001f469\u200d\U0001f467\u200d\U0001f466"


def _case_id(value):
    """A readable pytest id. Unprintable characters show as U+XXXX."""
    if value is None:
        return "none"
    if value == "":
        return "empty"
    parts = []
    letters = []

    def flush():
        if letters:
            parts.append("".join(letters))
            letters.clear()

    for char in value:
        if char.isprintable() and char != " ":
            letters.append(char)
            continue
        flush()
        if char == " ":
            parts.append("space")
        else:
            parts.append("U+%04X" % ord(char))
    flush()
    return "+".join(parts)


def _ids(values):
    return [_case_id(value) for value in values]


def _raise(value, **kwargs):
    options = {"field": "name", "max_len": 20}
    options.update(kwargs)
    with pytest.raises(TextValidationError) as caught:
        clean_text(value, **options)
    return caught.value


def test_codes_are_the_closed_set():
    assert TEXT_VALIDATION_CODES == (
        "blank",
        "too_long",
        "control_char",
        "bidi",
        "surrogate",
    )


def test_message_does_not_echo_the_input():
    """The sentence names the field. It does not repeat the text."""
    error = _raise("Zephyr\u202eQuill")
    message = str(error)
    assert error.code == "bidi"
    assert error.field == "name"
    assert "Zephyr" not in message
    assert "Quill" not in message
    assert "\u202e" not in message
    assert "name must not contain hidden or bidi controls" == message


@pytest.mark.parametrize(
    "char",
    ("\ud800", "\udfff"),
    ids=("U+D800", "U+DFFF"),
)
def test_surrogate_code(char):
    alone = _raise(char)
    assert alone.code == "surrogate"
    assert alone.field == "name"
    assert char not in str(alone)
    inside = _raise("A" + char + "B", field="body")
    assert inside.code == "surrogate"
    assert inside.field == "body"


@pytest.mark.parametrize("char", _BIDI + _HIDDEN, ids=_ids(_BIDI + _HIDDEN))
def test_bidi_and_hidden_format_codes(char):
    """A hidden mark next to a letter is rejected, not stored.

    U+E0000 is unassigned (Cn) in this Unicode data. It is still
    rejected because it sits in the tag-character block.
    """
    error = _raise("A" + char + "B", field="label")
    assert error.code == "bidi"
    assert error.field == "label"
    assert char not in str(error)
    if char != "\U000e0000":
        assert unicodedata.category(char) == "Cf"
    else:
        assert unicodedata.category(char) == "Cn"


@pytest.mark.parametrize(
    "char",
    ("\x00", "\x1b", "\x7f", "\n", "\r", "\t"),
    ids=_ids(("\x00", "\x1b", "\x7f", "\n", "\r", "\t")),
)
def test_control_code_without_newlines(char):
    error = _raise("A" + char + "B")
    assert error.code == "control_char"
    assert error.field == "name"
    assert char not in str(error)


def test_newline_controls_are_kept_when_newlines_are_allowed():
    kept = clean_text(
        "A\nB\rC\tD",
        field="body",
        max_len=20,
        allow_newlines=True,
    )
    assert kept == "A\nB\rC\tD"
    for char in ("\x00", "\x0b", "\x7f"):
        error = _raise(
            "A" + char + "B",
            field="body",
            allow_newlines=True,
        )
        assert error.code == "control_char"


def test_etf_newline_is_a_control_and_is_not_stripped():
    """The example from the contract. strip() would hide the newline."""
    error = _raise("ETF\n", allow_newlines=False)
    assert error.code == "control_char"
    assert (
        clean_text(
            "ETF\n",
            field="body",
            max_len=20,
            allow_newlines=True,
        )
        == "ETF"
    )


def test_check_order_is_surrogate_then_bidi_then_control_then_blank():
    """A later failure must not hide an earlier one."""
    assert _raise("\n\ud800").code == "surrogate"
    assert _raise("\x00\u202e").code == "bidi"
    assert _raise("\n").code == "control_char"
    assert _raise("  \n  ").code == "control_char"
    # Blank is decided after strip, and before the length check.
    # A long private-use-only value is blank, not too_long.
    assert _raise("\ue000" * 50, max_len=10).code == "blank"
    assert _raise("\n\ud800", allow_newlines=True).code == "surrogate"


def test_strip_then_length_ignores_surrounding_whitespace():
    assert clean_text("  hello  ", field="name", max_len=5) == "hello"
    assert clean_text(
        "  " + ("a" * 5) + "  ",
        field="name",
        max_len=5,
    ) == ("a" * 5)


def test_trailing_newline_on_a_single_line_never_reaches_length():
    error = _raise("  " + ("a" * 5) + "\n", max_len=5)
    assert error.code == "control_char"


def test_length_boundaries():
    assert clean_text("a" * 10, field="name", max_len=10) == "a" * 10
    error = _raise("a" * 11, max_len=10)
    assert error.code == "too_long"
    assert error.field == "name"
    assert "11" not in str(error)
    assert str(error) == "name must be at most 10 characters"
    padded = " " + ("a" * 10) + " "
    assert clean_text(padded, field="name", max_len=10) == "a" * 10
    over = _raise(" " + ("a" * 11), max_len=10)
    assert over.code == "too_long"


_BLANK_VALUES = (
    None,
    "",
    "   ",
    "\u00a0",
    "\u200b",
    "\ufeff",
    "\u200b \u200b",
    " \u200c\u200d ",
    "\ue000",
    "\ue000 \ue001",
    "\u0378",
    "\u0378 \u0379",
)


@pytest.mark.parametrize("value", _BLANK_VALUES, ids=_ids(_BLANK_VALUES))
def test_blank_values(value):
    error = _raise(value, allow_blank=False)
    assert error.code == "blank"
    assert error.field == "name"
    assert str(error) == "name must not be blank"
    assert (
        clean_text(value, field="label", max_len=80, allow_blank=True) is None
    )


def test_blank_categories_match_the_characters_under_test():
    """Co and Cn are the private-use and unassigned fillers."""
    assert unicodedata.category("\ue000") == "Co"
    assert unicodedata.category("\u0378") == "Cn"
    assert unicodedata.category("\u200b") == "Cf"


def test_co_and_cn_beside_a_letter_are_kept():
    """Do not reject them and do not strip them, including at an edge."""
    assert clean_text("A\ue000B", field="name", max_len=20) == "A\ue000B"
    assert clean_text("\ue000A", field="name", max_len=20) == "\ue000A"
    assert clean_text("A\u0378B", field="name", max_len=20) == "A\u0378B"
    assert clean_text("A\u0378", field="name", max_len=20) == "A\u0378"
    # Cf beside a letter follows the same keep rule.
    assert clean_text("A\u200bB", field="name", max_len=20) == "A\u200bB"
    assert clean_text("\u200bA\ufeff", field="name", max_len=20) == (
        "\u200bA\ufeff"
    )


def test_unknown_code_still_uses_a_safe_sentence():
    """A typo in a code must not fall through to echoing the input."""
    error = TextValidationError("nope", "name")
    assert error.code == "nope"
    assert error.field == "name"
    assert str(error) == "name is not valid text"


def test_non_string_is_a_programmer_error():
    with pytest.raises(TypeError):
        clean_text(5, field="name", max_len=20)  # type: ignore[arg-type]


def test_tag_block_rejects_u_e0001_and_keeps_u_e0080():
    """U+E0001 is inside U+E0000–U+E007F. U+E0080 is the next scalar.

    The next scalar is unassigned. Beside a letter it is kept.
    """
    rejected = _raise("A\U000e0001B", field="label")
    assert rejected.code == "bidi"
    assert rejected.field == "label"
    assert unicodedata.category("\U000e0001") == "Cf"
    assert (
        clean_text("A\U000e0080B", field="label", max_len=20) == "A\U000e0080B"
    )
    assert unicodedata.category("\U000e0080") == "Cn"


def test_nel_is_rejected_even_when_newlines_are_allowed():
    """U+0085 is category Cc. It is not newline, carriage return, or tab."""
    assert unicodedata.category("\u0085") == "Cc"
    error = _raise("A\u0085B", field="body", allow_newlines=True)
    assert error.code == "control_char"
    assert error.field == "body"
    assert "\u0085" not in str(error)


def test_line_separator_is_stripped_at_the_edge_and_kept_in_the_middle():
    """U+2028 is whitespace (category Zl), not a control character."""
    assert unicodedata.category("\u2028") == "Zl"
    assert (
        clean_text("\u2028Hello\u2028", field="title", max_len=20) == "Hello"
    )
    assert clean_text("A\u2028B", field="title", max_len=20) == "A\u2028B"


def test_max_len_counts_code_points_not_graphemes():
    """A ZWJ family emoji is one grapheme and seven code points."""
    assert len(_FAMILY) == 7
    assert [ord(char) for char in _FAMILY].count(0x200D) == 3
    assert clean_text(_FAMILY, field="name", max_len=7) == _FAMILY
    error = _raise(_FAMILY, max_len=6)
    assert error.code == "too_long"
    assert error.field == "name"
