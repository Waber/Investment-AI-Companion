"""Duplicate company errors shared by the repository and the HTTP API.

The ``/ui`` forms call the repository directly, so the stable machine
code lives on the exception. The companies API copies ``code`` onto
the 400 body. ``detail`` stays the same sentence on create and update.

These classes subclass ``ValueError``. An ``except ValueError`` that
already exists keeps working, and the caller can read ``error.code``.
"""


class DuplicateCompanyError(ValueError):
    """A ticker or ISIN is already stored on another company."""

    code: str


class DuplicateTickerError(DuplicateCompanyError):
    """Raised when the ticker is already stored."""

    code = "duplicate_ticker"

    def __init__(self) -> None:
        super().__init__("A company with this ticker already exists")


class DuplicateIsinError(DuplicateCompanyError):
    """Raised when the ISIN is already stored."""

    code = "duplicate_isin"

    def __init__(self) -> None:
        super().__init__("A company with this ISIN already exists")


DUPLICATE_TICKER_DETAIL = str(DuplicateTickerError())
DUPLICATE_ISIN_DETAIL = str(DuplicateIsinError())
