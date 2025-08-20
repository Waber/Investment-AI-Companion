from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from typing import List, Optional
from app.models.database_models import CompanyDB
from app.models.company import CompanyCreate, CompanyUpdate
from datetime import datetime, timezone

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
            IntegrityError: If company name or ticker already exists
        """
        # Create new CompanyDB instance
        db_company = CompanyDB(
            name=company.name,
            ticker=company.ticker,
            sector=company.sector,
            industry=company.industry,
            description=company.description,
            website=company.website,
            country=company.country,
            exchange=company.exchange,
            currency=company.currency or "USD"
        )
        
        # Add to database session
        self.db.add(db_company)
        
        try:
            # Commit the transaction
            self.db.commit()
            # Refresh the object to get database-generated values (id, timestamps)
            self.db.refresh(db_company)
            return db_company
        except IntegrityError as e:
            # Rollback on error
            self.db.rollback()
            # Re-raise with more specific error message
            if "uq_company_name_ticker" in str(e):
                raise ValueError("Company name or ticker already exists")
            raise
    
    def get_by_id(self, company_id: int) -> Optional[CompanyDB]:
        """
        Retrieve a company by its ID.
        
        Args:
            company_id: The unique identifier of the company
            
        Returns:
            CompanyDB or None: The company if found, None otherwise
        """
        return self.db.query(CompanyDB).filter(CompanyDB.id == company_id).first()
    
    def get_by_ticker(self, ticker: str) -> Optional[CompanyDB]:
        """
        Retrieve a company by its ticker symbol.
        
        Args:
            ticker: The stock ticker symbol
            
        Returns:
            CompanyDB or None: The company if found, None otherwise
        """
        return self.db.query(CompanyDB).filter(CompanyDB.ticker == ticker).first()
    
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
    
    def update(self, company_id: int, company_update: CompanyUpdate) -> Optional[CompanyDB]:
        """
        Update an existing company.
        
        Args:
            company_id: The ID of the company to update
            company_update: CompanyUpdate model with fields to update
            
        Returns:
            CompanyDB or None: The updated company if found, None otherwise
            
        Raises:
            IntegrityError: If update would violate unique constraints
        """
        # Get existing company
        db_company = self.get_by_id(company_id)
        if not db_company:
            return None
        
        # Update only the fields that were provided
        update_data = company_update.model_dump(exclude_unset=True)
        
        # Handle special case for name and ticker uniqueness
        if 'name' in update_data or 'ticker' in update_data:
            new_name = update_data.get('name', db_company.name)
            new_ticker = update_data.get('ticker', db_company.ticker)
            
            # Check if another company has the same name or ticker
            existing = self.db.query(CompanyDB).filter(
                CompanyDB.id != company_id,
                (CompanyDB.name == new_name) | (CompanyDB.ticker == new_ticker)
            ).first()
            
            if existing:
                raise ValueError("Company name or ticker already exists")
        
        # Update fields
        for field, value in update_data.items():
            setattr(db_company, field, value)
        
        # Update timestamp
        db_company.updated_at = datetime.now(timezone.utc)
        
        try:
            self.db.commit()
            self.db.refresh(db_company)
            return db_company
        except IntegrityError as e:
            self.db.rollback()
            raise ValueError("Update failed due to constraint violation")
    
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
    
    def is_unique(self, name: str, ticker: str, exclude_id: Optional[int] = None) -> bool:
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
