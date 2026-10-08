"""
API endpoints for data collection from external sources.

This module provides endpoints to fetch and sync data from various
financial data providers like Yahoo Finance.
"""

import logging
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

from app.core.database import get_db
from app.data_collectors.yahoo_finance import YahooFinanceCollector
from app.models.company import TICKER_PATTERN, normalize_ticker
from app.repositories.company_repository import CompanyRepository

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/data-collection", tags=["data-collection"])


def get_yahoo_finance_collector() -> YahooFinanceCollector:
    return YahooFinanceCollector()


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


class FetchCompanyResponse(BaseModel):
    """Response model for company data fetch."""

    success: bool
    message: str
    company_id: Optional[int] = None


@router.post("/fetch-company", response_model=FetchCompanyResponse)
def fetch_company_data(
    request: FetchCompanyRequest,
    db: Session = Depends(get_db),
    collector: YahooFinanceCollector = Depends(get_yahoo_finance_collector),
):
    """
    Fetch company data from Yahoo Finance and create/update it in the database.

    This endpoint:
    1. Fetches company information from Yahoo Finance
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
    ticker = request.ticker.upper()
    try:
        logger.info("Fetching company data for ticker: %r", ticker)

        # Initialize repository
        company_repo = CompanyRepository(db)

        # Fetch company info from Yahoo Finance
        company_info = collector.fetch_company_info(ticker)

        if not company_info:
            raise HTTPException(
                status_code=404,
                detail=(
                    f"Company with ticker {ticker} "
                    "not found on Yahoo Finance"
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
                description=company_info.get("description"),
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
                description=company_info.get("description"),
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
    except ValueError as e:
        # Handle uniqueness violations. The message is a fixed business
        # error, not a provider traceback, so it stays in the response.
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        # The client gets a fixed sentence. The traceback, including
        # anything the provider put in the exception, stays in the log.
        # %r keeps a newline in the ticker from starting a new log line.
        logger.exception("Error fetching company data for ticker %r", ticker)
        raise HTTPException(
            status_code=500, detail="Error fetching company data"
        )


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
