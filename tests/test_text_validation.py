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


@pytest.mark.parametrize("char", ("\ud800", "\udfff"))
def test_surrogate_code(char):
    alone = _raise(char)
    assert alone.code == "surrogate"
    assert alone.field == "name"
    assert char not in str(alone)
    inside = _raise("A" + char + "B", field="body")
    assert inside.code == "surrogate"
    assert inside.field == "body"


@pytest.mark.parametrize("char", _BIDI + _HIDDEN)
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


@pytest.mark.parametrize("char", ("\x00", "\x1b", "\x7f", "\n", "\r", "\t"))
def test_control_code_without_newlines(char):
    error = _raise("A" + char + "B")
    assert error.code == "control_char"
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


@pytest.mark.parametrize(
    "value",
    [
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
    ],
)
def test_blank_values(value):
    error = _raise(value, allow_blank=False)
    assert error.code == "blank"
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
