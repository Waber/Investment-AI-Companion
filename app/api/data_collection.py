"""
API endpoints for data collection from external sources.

This module provides endpoints to fetch and sync data from various
financial data providers like Yahoo Finance.
"""

import logging
import threading
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    field_validator,
)
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.data_collectors.base import InstrumentLookup, ProviderError
from app.data_collectors.fake import FakeCollector
from app.data_collectors.guard import GuardPolicy, guard_collector
from app.data_collectors.yahoo_finance import YahooFinanceCollector
from app.models.company import (
    DESCRIPTION_MAX_LENGTH,
    TICKER_PATTERN,
    normalize_ticker,
)
from app.repositories.company_repository import CompanyRepository

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/data-collection", tags=["data-collection"])


# fetch-company in "yahoo" mode uses one guarded Yahoo collector for
# every request, so the cache and the rate limit see all of them. It is
# a module-level variable (like a static field in Java), built on first
# use from the settings. The lock stops two first requests from each
# building one.
_shared_collector: Optional[InstrumentLookup] = None
_shared_collector_lock = threading.Lock()


def get_collector() -> InstrumentLookup:
    """Return the collector chosen by ``DATA_COLLECTOR``.

    ``fake`` gives a new offline ``FakeCollector``. It is not guarded:
    it never calls the network. ``yahoo`` gives the shared Yahoo
    collector behind the cache, rate limit and retries of
    ``app.data_collectors.guard``.

    The setting is read on every call (not at import), so a test can
    change it with ``monkeypatch``. Tests that need other behavior
    replace this function through ``app.dependency_overrides``.
    """
    if settings.DATA_COLLECTOR == "fake":
        return FakeCollector()
    return _shared_yahoo_collector()


def _shared_yahoo_collector() -> InstrumentLookup:
    # "global" lets this function assign the module-level variable;
    # without it the assignment would create a local variable.
    global _shared_collector
    with _shared_collector_lock:
        if _shared_collector is None:
            _shared_collector = guard_collector(
                YahooFinanceCollector(), GuardPolicy.from_settings(settings)
            )
        return _shared_collector


def reset_collector() -> None:
    """Forget the shared Yahoo collector, with its cache and rate limit.

    The next ``yahoo`` request builds a new one from the current
    settings. Tests call this around every test.
    """
    global _shared_collector
    with _shared_collector_lock:
        _shared_collector = None


class FetchCompanyRequest(BaseModel):
    """Request model for fetching company data."""

    ticker: str = Field(..., pattern=TICKER_PATTERN)

    model_config = ConfigDict(
        json_schema_extra={"example": {"ticker": "AAPL"}}
    )

    @field_validator("ticker", mode="before")
    @classmethod
    def _normalize_ticker(cls, value: object) -> object:
        return normalize_ticker(value)


def _log_provider_validation(ticker: str, exc: ValidationError) -> None:
    """Log which fields failed, not the provider's raw values.

    ``ValidationError`` text includes the input. That text must stay
    out of the HTTP body and out of this log line.
    """
    fields = []
    kinds = []
    for err in exc.errors():
        location = err.get("loc") or ()
        fields.append(".".join(str(part) for part in location))
        kinds.append(str(err.get("type", "value_error")))
    logger.error(
        "Provider returned invalid company data for ticker %r "
        "fields=%r types=%r",
        ticker,
        fields,
        kinds,
    )


def _provider_description(company_info: dict) -> object:
    """Keep the first 5000 characters of a provider summary.

    The 5000-character cap is for user create and update, which still
    return HTTP 422. Yahoo's ``longBusinessSummary`` can be longer.
    Passing it through ``CompanyCreate`` would be a validation error
    and fetch-company would return HTTP 502. There is no ellipsis:
    the stored text is exactly the first ``DESCRIPTION_MAX_LENGTH``
    characters.
    """
    description = company_info.get("description")
    if not isinstance(description, str):
        return description
    if len(description) <= DESCRIPTION_MAX_LENGTH:
        return description
    return description[:DESCRIPTION_MAX_LENGTH]


class FetchCompanyResponse(BaseModel):
    """Response model for company data fetch."""

    success: bool
    message: str
    company_id: Optional[int] = None


@router.post("/fetch-company", response_model=FetchCompanyResponse)
def fetch_company_data(
    request: FetchCompanyRequest,
    db: Session = Depends(get_db),
    collector: InstrumentLookup = Depends(get_collector),
):
    """
    Fetch company data from the configured provider and create/update it.

    The provider is chosen by ``DATA_COLLECTOR`` (``yahoo`` or ``fake``).

    This endpoint:
    1. Fetches company information from the provider
    2. Creates a new company in the database if it doesn't exist
    3. Updates existing company if it already exists
    4. Returns the company ID

    Args:
        request: FetchCompanyRequest with ticker symbol
        db: Database session

    Returns:
        FetchCompanyResponse with success status and company ID

    Example:
        POST /data-collection/fetch-company
        {
            "ticker": "AAPL"
        }
    """
    # Bound before the try so the error log can name the ticker even
    # when the failure is the first line of the body.
    # FetchCompanyRequest already strips and uppercases. Doing it again
    # would change a ticker that bypassed validation.
    ticker = request.ticker
    try:
        logger.info("Fetching company data for ticker: %r", ticker)

        # Initialize repository
        company_repo = CompanyRepository(db)

        # Fetch company info from Yahoo Finance
        # The collector returns the data together with its provenance.
        # This endpoint stores only the data, so it reads ``.value``.
        result = collector.fetch_company_info(ticker)
        company_info = result.value if result is not None else None

        if not company_info:
            raise HTTPException(
                status_code=404,
                detail=(
                    f"Company with ticker {ticker} "
                    "not found at the data provider"
                ),
            )

        # Check if company already exists
        existing_company = company_repo.get_by_ticker(ticker)

        if existing_company:
            # Update existing company
            logger.info("Updating existing company with ticker: %r", ticker)
            from app.models.company import CompanyUpdate

            # Prepare update data using CompanyUpdate model
            update_data = CompanyUpdate(
                name=company_info.get("name"),
                sector=company_info.get("sector"),
                industry=company_info.get("industry"),
                description=_provider_description(company_info),
                website=company_info.get("website"),
                country=company_info.get("country"),
                exchange=company_info.get("exchange"),
                currency=company_info.get("currency", "USD"),
            )

            # Update company
            updated_company = company_repo.update(
                existing_company.id, update_data
            )

            if not updated_company:
                logger.error("Failed to update company for ticker %r", ticker)
                raise HTTPException(
                    status_code=500, detail="Failed to update company"
                )

            logger.info(
                "Successfully updated company: %r", updated_company.name
            )
            return FetchCompanyResponse(
                success=True,
                message=f"Company {updated_company.name} updated successfully",
                company_id=updated_company.id,
            )

        else:
            # Create new company
            logger.info("Creating new company with ticker: %r", ticker)
            from app.models.company import CompanyCreate

            company_create = CompanyCreate(
                name=company_info.get("name"),
                ticker=ticker,
                sector=company_info.get("sector"),
                industry=company_info.get("industry"),
                description=_provider_description(company_info),
                website=company_info.get("website"),
                country=company_info.get("country"),
                exchange=company_info.get("exchange"),
                currency=company_info.get("currency", "USD"),
            )

            # Create company
            new_company = company_repo.create(company_create)

            logger.info("Successfully created company: %r", new_company.name)
            return FetchCompanyResponse(
                success=True,
                message=f"Company {new_company.name} created successfully",
                company_id=new_company.id,
            )

    except HTTPException:
        raise
    except ValidationError as exc:
        # ValidationError subclasses ValueError. It has to be caught
        # first, or a bad provider payload is returned as HTTP 400 with
        # the provider's own text in the body.
        _log_provider_validation(ticker, exc)
        raise HTTPException(
            status_code=502,
            detail="Provider returned invalid company data",
        )
    except ProviderError:
        # ProviderError is not a ValueError, so it is not a 400. The
        # provider's own text (the exception cause) stays out of the
        # body and out of this line: the collector already logged it in
        # its own module. %r keeps the ticker on one log line.
        logger.error("Data provider error for ticker %r", ticker)
        raise HTTPException(status_code=502, detail="Data provider error")
    except ValueError as e:
        # Handle uniqueness violations. The message is a fixed business
        # error, not a provider traceback, so it stays in the response.
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as exc:
        # An unexpected error used to be HTTP 500 with the traceback in
        # the log. The traceback can include provider text. The client
        # gets the same fixed sentence as a ProviderError, and the log
        # keeps the class name only. %r keeps a newline in the ticker
        # from starting a new log line.
        logger.error(
            "Unexpected %s fetching company data for ticker %r",
            type(exc).__name__,
            ticker,
        )
        raise HTTPException(
            status_code=502, detail="Data provider error"
        ) from None


@router.post("/fetch-financial-metrics")
def fetch_financial_metrics(
    request: FetchCompanyRequest, db: Session = Depends(get_db)
):
    """
    Fetch financial metrics from Yahoo Finance for a company.

    Note: This endpoint is a placeholder for future implementation.
    Financial metrics integration will require careful mapping of Yahoo Finance
    data to our database schema.

    Args:
        request: FetchCompanyRequest with ticker symbol
        db: Database session

    Returns:
        Dictionary with financial metrics
    """
    return {
        "message": "This endpoint is not yet implemented",
        "ticker": request.ticker,
    }
