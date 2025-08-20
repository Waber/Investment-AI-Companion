from fastapi import APIRouter, HTTPException, status, Depends
from typing import List, Optional
from sqlalchemy.orm import Session
from app.models.financial_metrics import FinancialMetrics, FinancialMetricsCreate, FinancialMetricsUpdate
from app.models.database_models import FinancialMetricsDB
from app.repositories.financial_metrics_repository import FinancialMetricsRepository
from app.core.database import get_db
from datetime import datetime, timezone

router = APIRouter(prefix="/financial-metrics", tags=["financial-metrics"])

# Helper function to convert FinancialMetricsDB to FinancialMetrics Pydantic model
def db_to_metrics_model(db_metrics: FinancialMetricsDB) -> FinancialMetrics:
    """
    Convert SQLAlchemy FinancialMetricsDB model to Pydantic FinancialMetrics model.
    This handles the conversion between database and API models.
    """
    return FinancialMetrics(
        id=db_metrics.id,
        company_id=db_metrics.company_id,
        period_end=db_metrics.period_end,
        period_type=db_metrics.period_type,
        revenue=db_metrics.revenue,
        net_income=db_metrics.net_income,
        total_assets=db_metrics.total_assets,
        total_liabilities=db_metrics.total_liabilities,
        total_equity=db_metrics.total_equity,
        roe=db_metrics.roe,
        roa=db_metrics.roa,
        gross_margin=db_metrics.gross_margin,
        net_margin=db_metrics.net_margin,
        current_ratio=db_metrics.current_ratio,
        quick_ratio=db_metrics.quick_ratio,
        debt_to_equity=db_metrics.debt_to_equity,
        debt_to_assets=db_metrics.debt_to_assets,
        asset_turnover=db_metrics.asset_turnover,
        inventory_turnover=db_metrics.inventory_turnover,
        revenue_growth=db_metrics.revenue_growth,
        net_income_growth=db_metrics.net_income_growth,
        pe_ratio=db_metrics.pe_ratio,
        pb_ratio=db_metrics.pb_ratio,
        ev_ebitda=db_metrics.ev_ebitda,
        created_at=db_metrics.created_at,
        updated_at=db_metrics.updated_at
    )

@router.get("/", response_model=List[FinancialMetrics])
def list_financial_metrics(
    skip: int = 0, 
    limit: int = 100, 
    db: Session = Depends(get_db)
):
    """
    Retrieve a list of financial metrics with pagination support.
    
    Args:
        skip: Number of records to skip (for pagination)
        limit: Maximum number of records to return
        db: Database session injected by FastAPI dependency
        
    Returns:
        List[FinancialMetrics]: List of financial metrics
    """
    repo = FinancialMetricsRepository(db)
    db_metrics = repo.get_all(skip=skip, limit=limit)
    return [db_to_metrics_model(metrics) for metrics in db_metrics]

@router.get("/{metrics_id}", response_model=FinancialMetrics)
def get_financial_metrics(metrics_id: int, db: Session = Depends(get_db)):
    """
    Retrieve specific financial metrics by ID.
    
    Args:
        metrics_id: The unique identifier of the metrics
        db: Database session injected by FastAPI dependency
        
    Returns:
        FinancialMetrics: The financial metrics data
        
    Raises:
        HTTPException: 404 if metrics not found
    """
    repo = FinancialMetricsRepository(db)
    db_metrics = repo.get_by_id(metrics_id)
    
    if not db_metrics:
        raise HTTPException(status_code=404, detail="Financial metrics not found")
    
    return db_to_metrics_model(db_metrics)

@router.get("/company/{company_id}", response_model=List[FinancialMetrics])
def get_company_financial_metrics(
    company_id: int, 
    skip: int = 0, 
    limit: int = 100, 
    db: Session = Depends(get_db)
):
    """
    Retrieve all financial metrics for a specific company.
    
    Args:
        company_id: The ID of the company
        skip: Number of records to skip (for pagination)
        limit: Maximum number of records to return
        db: Database session injected by FastAPI dependency
        
    Returns:
        List[FinancialMetrics]: List of financial metrics for the company
    """
    repo = FinancialMetricsRepository(db)
    db_metrics = repo.get_by_company(company_id, skip=skip, limit=limit)
    return [db_to_metrics_model(metrics) for metrics in db_metrics]

@router.post("/", response_model=FinancialMetrics, status_code=status.HTTP_201_CREATED)
def create_financial_metrics(metrics: FinancialMetricsCreate, db: Session = Depends(get_db)):
    """
    Create new financial metrics.
    
    Args:
        metrics: Financial metrics data from request body
        db: Database session injected by FastAPI dependency
        
    Returns:
        FinancialMetrics: The created metrics with generated fields
        
    Raises:
        HTTPException: 400 if metrics already exist for this company/period
    """
    repo = FinancialMetricsRepository(db)
    
    try:
        db_metrics = repo.create(metrics)
        return db_to_metrics_model(db_metrics)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error")

@router.put("/{metrics_id}", response_model=FinancialMetrics)
def update_financial_metrics(metrics_id: int, metrics: FinancialMetricsUpdate, db: Session = Depends(get_db)):
    """
    Update existing financial metrics.
    
    Args:
        metrics_id: The ID of the metrics to update
        metrics: Updated metrics data
        db: Database session injected by FastAPI dependency
        
    Returns:
        FinancialMetrics: The updated metrics
        
    Raises:
        HTTPException: 404 if metrics not found, 400 if update fails
    """
    repo = FinancialMetricsRepository(db)
    
    try:
        db_metrics = repo.update(metrics_id, metrics)
        
        if not db_metrics:
            raise HTTPException(status_code=404, detail="Financial metrics not found")
        
        return db_to_metrics_model(db_metrics)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error")

@router.delete("/{metrics_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_financial_metrics(metrics_id: int, db: Session = Depends(get_db)):
    """
    Delete financial metrics by ID.
    
    Args:
        metrics_id: The ID of the metrics to delete
        db: Database session injected by FastAPI dependency
        
    Raises:
        HTTPException: 404 if metrics not found
    """
    repo = FinancialMetricsRepository(db)
    
    if not repo.delete(metrics_id):
        raise HTTPException(status_code=404, detail="Financial metrics not found")
    
    # Return 204 No Content on successful deletion 