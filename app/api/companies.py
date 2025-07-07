from fastapi import APIRouter, HTTPException, status
from typing import List
from app.models.company import Company, CompanyCreate, CompanyUpdate
from datetime import datetime

router = APIRouter(prefix="/companies", tags=["companies"])

# In-memory storage (tymczasowo, do podmiany na bazę danych)
companies_db: List[Company] = []
company_id_seq = 1

def is_unique_company(name: str, ticker: str, exclude_id: int = None) -> bool:
    for c in companies_db:
        if exclude_id is not None and c.id == exclude_id:
            continue
        if c.name.lower() == name.lower() or c.ticker.lower() == ticker.lower():
            return False
    return True

@router.get("/", response_model=List[Company])
def list_companies():
    return companies_db

@router.get("/{company_id}", response_model=Company)
def get_company(company_id: int):
    for c in companies_db:
        if c.id == company_id:
            return c
    raise HTTPException(status_code=404, detail="Company not found")

@router.post("/", response_model=Company, status_code=status.HTTP_201_CREATED)
def create_company(company: CompanyCreate):
    global company_id_seq
    if not is_unique_company(company.name, company.ticker):
        raise HTTPException(status_code=400, detail="Company name or ticker must be unique")
    new_company = Company(
        id=company_id_seq,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
        is_active=True,
        last_data_update=None,
        **company.dict()
    )
    companies_db.append(new_company)
    company_id_seq += 1
    return new_company

@router.put("/{company_id}", response_model=Company)
def update_company(company_id: int, company: CompanyUpdate):
    for idx, c in enumerate(companies_db):
        if c.id == company_id:
            # Walidacja unikalności (pomijamy aktualizowaną firmę)
            if not is_unique_company(company.name or c.name, company.ticker or c.ticker, exclude_id=company_id):
                raise HTTPException(status_code=400, detail="Company name or ticker must be unique")
            updated = c.copy(update=company.dict(exclude_unset=True))
            updated.updated_at = datetime.utcnow()
            companies_db[idx] = updated
            return updated
    raise HTTPException(status_code=404, detail="Company not found")

@router.delete("/{company_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_company(company_id: int):
    for idx, c in enumerate(companies_db):
        if c.id == company_id:
            del companies_db[idx]
            return
    raise HTTPException(status_code=404, detail="Company not found")
