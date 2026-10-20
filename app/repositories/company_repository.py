from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.company import CompanyCreate, CompanyUpdate, InstrumentType
from app.models.database_models import CompanyDB


def _serialize_optional_url(value):
    return str(value) if value is not None else None


DUPLICATE_ISIN_DETAIL = "A company with this ISIN already exists"
DUPLICATE_TICKER_DETAIL = "A company with this ticker already exists"


def _instrument_type_value(value):
    """Store the enum as the three-letter string the column expects."""
    if isinstance(value, InstrumentType):
        return value.value
    if value is None:
        return InstrumentType.STOCK.value
    return value


def _duplicate_detail(repository, ticker, isin, exclude_id=None):
    """Return the client sentence when this ticker or ISIN is already stored.

    Create passes no ``exclude_id``, so any stored row is a duplicate.
    Update passes the row being changed, and that row is not a
    duplicate of itself. A missing ISIN is not looked up: a comparison
    with None would match every company that has no ISIN.
    """
    taken = repository.get_by_ticker(ticker)
    if taken is not None and taken.id != exclude_id:
        return DUPLICATE_TICKER_DETAIL
    if isin is not None:
        taken = repository.get_by_isin(isin)
        if taken is not None and taken.id != exclude_id:
            return DUPLICATE_ISIN_DETAIL
    return None


class CompanyRepository:
    """
    Repository class for company-related database operations.
    This layer abstracts database logic from the API endpoints.

    Key benefits:
    - Separates business logic from data access
    - Makes testing easier (can mock the repository)
    - Centralizes database operations
    - Handles database-specific errors
    """

    def __init__(self, db: Session):
        self.db = db

    def create(self, company: CompanyCreate) -> CompanyDB:
        """
        Create a new company in the database.

        Args:
            company: CompanyCreate model with company data

        Returns:
            CompanyDB: The created company with database-generated fields (id, timestamps)

        Raises:
            ValueError: If this ticker or ISIN is already stored
            IntegrityError: If some other constraint fails
        """
        # Look up before insert. The unique index is a backstop for
        # two creates that pass this check at the same time.
        detail = _duplicate_detail(self, company.ticker, company.isin)
        if detail is not None:
            raise ValueError(detail)

        # Create new CompanyDB instance
        db_company = CompanyDB(
            name=company.name,
            ticker=company.ticker,
            sector=company.sector,
            industry=company.industry,
            description=company.description,
            website=_serialize_optional_url(company.website),
            country=company.country,
            exchange=company.exchange,
            currency=company.currency or "USD",
            instrument_type=_instrument_type_value(company.instrument_type),
            isin=company.isin,
        )

        # Add to database session
        self.db.add(db_company)

        try:
            # Commit the transaction
            self.db.commit()
            # Refresh the object to get database-generated values (id, timestamps)
            self.db.refresh(db_company)
            return db_company
        except IntegrityError:
            # The driver text names whatever index fired. SQLite and
            # PostgreSQL use different names, and neither is safe to
            # copy into an HTTP response. After rollback, a row that
            # is already stored is a client error. Anything else is
            # still an unexpected database error.
            self.db.rollback()
            detail = _duplicate_detail(self, company.ticker, company.isin)
            if detail is not None:
                raise ValueError(detail) from None
            raise

    def get_by_id(self, company_id: int) -> Optional[CompanyDB]:
        """
        Retrieve a company by its ID.

        Args:
            company_id: The unique identifier of the company

        Returns:
            CompanyDB or None: The company if found, None otherwise
        """
        return (
            self.db.query(CompanyDB).filter(CompanyDB.id == company_id).first()
        )

    def get_by_ticker(self, ticker: str) -> Optional[CompanyDB]:
        """
        Retrieve a company by its ticker symbol.

        Args:
            ticker: The stock ticker symbol

        Returns:
            CompanyDB or None: The company if found, None otherwise
        """
        return (
            self.db.query(CompanyDB).filter(CompanyDB.ticker == ticker).first()
        )

    def get_by_isin(self, isin: str) -> Optional[CompanyDB]:
        """Return the company that already stores this ISIN, if any."""
        return self.db.query(CompanyDB).filter(CompanyDB.isin == isin).first()

    def get_all(self, skip: int = 0, limit: int = 100) -> List[CompanyDB]:
        """
        Retrieve all companies with pagination support.

        Args:
            skip: Number of records to skip (for pagination)
            limit: Maximum number of records to return

        Returns:
            List[CompanyDB]: List of companies
        """
        return self.db.query(CompanyDB).offset(skip).limit(limit).all()

    def update(
        self, company_id: int, company_update: CompanyUpdate
    ) -> Optional[CompanyDB]:
        """
        Update an existing company.

        Args:
            company_id: The ID of the company to update
            company_update: CompanyUpdate model with fields to update

        Returns:
            CompanyDB or None: The updated company if found, None otherwise

        Raises:
            ValueError: If this ticker or ISIN is already stored, or
                another constraint fails
        """
        # Get existing company
        db_company = self.get_by_id(company_id)
        if not db_company:
            return None

        # Update only the fields that were provided
        update_data = company_update.model_dump(exclude_unset=True)
        if "website" in update_data:
            update_data["website"] = _serialize_optional_url(
                update_data["website"]
            )
        if "instrument_type" in update_data:
            update_data["instrument_type"] = _instrument_type_value(
                update_data["instrument_type"]
            )

        # Handle special case for name and ticker uniqueness
        if "name" in update_data or "ticker" in update_data:
            new_name = update_data.get("name", db_company.name)
            new_ticker = update_data.get("ticker", db_company.ticker)
            if self._another_company_has_name_or_ticker(
                company_id, new_name, new_ticker
            ):
                raise ValueError("Company name or ticker already exists")

        if update_data.get("isin") is not None:
            taken = self.get_by_isin(update_data["isin"])
            if taken is not None and taken.id != company_id:
                raise ValueError(DUPLICATE_ISIN_DETAIL)

        # Update fields
        for field, value in update_data.items():
            setattr(db_company, field, value)

        # Update timestamp
        db_company.updated_at = datetime.now(timezone.utc)

        try:
            self.db.commit()
            self.db.refresh(db_company)
            return db_company
        except IntegrityError:
            # Same lookup as create. The driver text is not read:
            # SQLite and PostgreSQL name the index differently.
            # A stored ticker or ISIN is a client error. Anything
            # else keeps the generic sentence, including a NOT NULL
            # failure, so it is not reported as a duplicate ticker.
            self.db.rollback()
            detail = _duplicate_detail(
                self,
                update_data.get("ticker", db_company.ticker),
                (
                    update_data["isin"]
                    if "isin" in update_data
                    else db_company.isin
                ),
                exclude_id=company_id,
            )
            if detail is not None:
                raise ValueError(detail) from None
            raise ValueError("Update failed due to constraint violation")

    def _another_company_has_name_or_ticker(self, company_id, name, ticker):
        """True when a different row already uses this name or ticker."""
        return (
            self.db.query(CompanyDB)
            .filter(
                CompanyDB.id != company_id,
                (CompanyDB.name == name) | (CompanyDB.ticker == ticker),
            )
            .first()
            is not None
        )

    def delete(self, company_id: int) -> bool:
        """
        Delete a company by ID.

        Args:
            company_id: The ID of the company to delete

        Returns:
            bool: True if company was deleted, False if not found
        """
        db_company = self.get_by_id(company_id)
        if not db_company:
            return False

        # Delete the company (cascade will handle related financial metrics)
        self.db.delete(db_company)
        self.db.commit()
        return True

    def is_unique(
        self, name: str, ticker: str, exclude_id: Optional[int] = None
    ) -> bool:
        """
        Check if company name and ticker are unique.

        Args:
            name: Company name to check
            ticker: Ticker symbol to check
            exclude_id: Company ID to exclude from uniqueness check (for updates)

        Returns:
            bool: True if unique, False otherwise
        """
        query = self.db.query(CompanyDB).filter(
            (CompanyDB.name == name) | (CompanyDB.ticker == ticker)
        )

        if exclude_id:
            query = query.filter(CompanyDB.id != exclude_id)

        return not query.first()
