"""ISO 6166 ISIN checks used at the company write boundary.

The examples are published identifiers. They pin the checksum. They
are not holdings and they are not a suggestion to buy or sell.
"""

import pytest

from app.models.company import isin_checksum_is_valid, normalize_isin

# Check digits confirmed against the ISO 6166 Luhn expansion.
VALID_ISINS = (
    "US0378331005",
    "DE0007164600",
    "IE00B4L5Y983",
    "GB0002634946",
    "DE000A0S9GB0",
)


@pytest.mark.parametrize("isin", VALID_ISINS)
def test_published_isins_pass_the_checksum(isin):
    assert isin_checksum_is_valid(isin) is True


def test_checksum_rejects_a_wrong_check_digit_and_lowercase():
    assert isin_checksum_is_valid("US0378331006") is False
    # The helper does not uppercase. The write normalizer does that.
    assert isin_checksum_is_valid("us0378331005") is False
    assert isin_checksum_is_valid("US037833100") is False


def test_normalize_uppercases_and_strips_a_valid_isin():
    assert normalize_isin("  us0378331005  ") == "US0378331005"
    assert normalize_isin("ie00b4l5y983") == "IE00B4L5Y983"


def test_normalize_leaves_none_and_non_strings_alone():
    assert normalize_isin(None) is None
    assert normalize_isin(12) == 12


@pytest.mark.parametrize(
    ("value", "message"),
    [
        ("US0378331006", "checksum is invalid"),
        ("US037833100", "12 characters"),
        ("US03783310055", "12 characters"),
        ("12ABCDEFGHI3", "12 characters"),
        ("", "12 characters"),
        ("   ", "12 characters"),
        ("US0378331005\n", "control characters"),
        ("US0378331005\x7f", "control characters"),
        ("US037833100５", "ASCII"),
        ("é0378331005", "ASCII"),
        ("US0378331005\u00a0", "ASCII"),
    ],
)
def test_normalize_rejects_isin_that_is_not_a_real_code(value, message):
    with pytest.raises(ValueError, match=message):
        normalize_isin(value)
