"""Company errors shared by repositories and the HTTP API.

The ``/ui`` forms call the repository directly, so the stable machine
code lives on the exception. The companies API copies ``code`` onto
the 400 body. ``detail`` stays the same sentence on create and update.

The duplicate classes subclass ``ValueError``. An ``except ValueError``
that already exists keeps working, and the caller can read ``error.code``.

``CompanyNotFoundError`` subclasses ``LookupError``, not ``ValueError``.
A handler that already catches duplicate-name ``ValueError`` does not
swallow a missing company.
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


class CompanyNotFoundError(LookupError):
    """Raised when a company id is not stored.

    ``company_id`` is the id that was looked up. The message is the
    same on SQLite and PostgreSQL. This is not an ``IntegrityError``
    and it does not include driver text.
    """

    def __init__(self, company_id: int) -> None:
        self.company_id = company_id
        super().__init__("Company {} was not found".format(company_id))
