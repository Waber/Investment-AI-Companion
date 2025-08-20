from fastapi import APIRouter, HTTPException, status, Depends
from typing import List, Optional
from sqlalchemy.orm import Session
from app.models.company import Company, CompanyCreate, CompanyUpdate
from app.models.database_models import CompanyDB
from app.repositories.company_repository import CompanyRepository
from app.core.database import get_db
from datetime import datetime, timezone

router = APIRouter(prefix="/companies", tags=["companies"])

# Helper function to convert CompanyDB to Company Pydantic model
def db_to_company_model(db_company: CompanyDB) -> Company:
    """
    Convert SQLAlchemy CompanyDB model to Pydantic Company model.
    This is needed because our API returns Pydantic models, but our repository works with SQLAlchemy models.
    
    The conversion handles:
    - Field mapping between database and API models
    - Type conversions if needed
    - Any additional transformations
    """
    return Company(
        id=db_company.id,
        name=db_company.name,
        ticker=db_company.ticker,
        sector=db_company.sector,
        industry=db_company.industry,
        description=db_company.description,
        website=db_company.website,
        country=db_company.country,
        exchange=db_company.exchange,
        currency=db_company.currency,
        created_at=db_company.created_at,
        updated_at=db_company.updated_at,
        is_active=db_company.is_active,
        last_data_update=db_company.last_data_update# does this have to be done manually? Can it be done automatically by some mapper?
    )

@router.get("/", response_model=List[Company])
def list_companies(
    skip: int = 0, 
    limit: int = 100, 
    db: Session = Depends(get_db)
):
    """
    Retrieve a list of companies with pagination support.
    
    Args:
        skip: Number of records to skip (for pagination)
        limit: Maximum number of records to return
        db: Database session injected by FastAPI dependency
        
    Returns:
        List[Company]: List of companies
    """
    # Create repository instance with the database session
    repo = CompanyRepository(db)
    
    # Get companies from database using repository
    db_companies = repo.get_all(skip=skip, limit=limit)
    
    # Convert database models to API models
    return [db_to_company_model(company) for company in db_companies]

@router.get("/{company_id}", response_model=Company)
def get_company(company_id: int, db: Session = Depends(get_db)):
    """
    Retrieve a specific company by ID.
    
    Args:
        company_id: The unique identifier of the company
        db: Database session injected by FastAPI dependency
        
    Returns:
        Company: The company data
        
    Raises:
        HTTPException: 404 if company not found
    """
    repo = CompanyRepository(db)
    db_company = repo.get_by_id(company_id)
    
    if not db_company:
        raise HTTPException(status_code=404, detail="Company not found")
    
    return db_to_company_model(db_company)

@router.post("/", response_model=Company, status_code=status.HTTP_201_CREATED)
def create_company(company: CompanyCreate, db: Session = Depends(get_db)):
    """
    Create a new company.
    
    Args:
        company: Company data from request body
        db: Database session injected by FastAPI dependency
        
    Returns:
        Company: The created company with generated fields (id, timestamps)
        
    Raises:
        HTTPException: 400 if company name or ticker already exists
    """
    repo = CompanyRepository(db)
    
    try:
        # Create company using repository
        db_company = repo.create(company)
        return db_to_company_model(db_company)
    except ValueError as e:
        # Handle business logic errors (e.g., duplicate name/ticker)
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        # Handle unexpected errors
        raise HTTPException(status_code=500, detail="Internal server error")

@router.put("/{company_id}", response_model=Company)
def update_company(company_id: int, company: CompanyUpdate, db: Session = Depends(get_db)):
    """
    Update an existing company.
    
    Args:
        company_id: The ID of the company to update
        company: Updated company data
        db: Database session injected by FastAPI dependency
        
    Returns:
        Company: The updated company
        
    Raises:
        HTTPException: 404 if company not found, 400 if update fails
    """
    repo = CompanyRepository(db)
    
    try:
        # Update company using repository
        db_company = repo.update(company_id, company)
        
        if not db_company:
            raise HTTPException(status_code=404, detail="Company not found")
        
        return db_to_company_model(db_company)
    except ValueError as e:
        # Handle business logic errors
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        # Handle unexpected errors
        raise HTTPException(status_code=500, detail="Internal server error")

@router.delete("/{company_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_company(company_id: int, db: Session = Depends(get_db)):
    """
    Delete a company by ID.
    
    Args:
        company_id: The ID of the company to delete
        db: Database session injected by FastAPI dependency
        
    Raises:
        HTTPException: 404 if company not found
    """
    repo = CompanyRepository(db)
    
    # Delete company using repository
    if not repo.delete(company_id):
        raise HTTPException(status_code=404, detail="Company not found")
    
    # Return 204 No Content on successful deletion
