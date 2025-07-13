from fastapi import APIRouter, HTTPException, status
from typing import List, Optional
from app.models.financial_metrics import FinancialMetrics, FinancialMetricsCreate, FinancialMetricsUpdate
from datetime import datetime, timezone

router = APIRouter(prefix="/financial-metrics", tags=["financial-metrics"])

# In-memory storage (temporarily, to be replaced with database)
financial_metrics_db: List[FinancialMetrics] = []
metrics_id_seq = 1

def is_unique_metrics(company_id: int, period_end: datetime, period_type: str, exclude_id: Optional[int] = None) -> bool:
    for m in financial_metrics_db:
        if exclude_id is not None and m.id == exclude_id:
            continue
        if (m.company_id == company_id and 
            m.period_end == period_end and 
            m.period_type == period_type):
            return False
    return True

@router.get("/", response_model=List[FinancialMetrics])
def list_financial_metrics():
    return financial_metrics_db

@router.get("/{metrics_id}", response_model=FinancialMetrics)
def get_financial_metrics(metrics_id: int):
    for m in financial_metrics_db:
        if m.id == metrics_id:
            return m
    raise HTTPException(status_code=404, detail="Financial metrics not found")

@router.get("/company/{company_id}", response_model=List[FinancialMetrics])
def get_company_financial_metrics(company_id: int):
    metrics = [m for m in financial_metrics_db if m.company_id == company_id]
    return metrics

@router.post("/", response_model=FinancialMetrics, status_code=status.HTTP_201_CREATED)
def create_financial_metrics(metrics: FinancialMetricsCreate):
    global metrics_id_seq
    if not is_unique_metrics(metrics.company_id, metrics.period_end, metrics.period_type):
        raise HTTPException(
            status_code=400, 
            detail="Financial metrics for this company, period end, and period type must be unique"
        )
    
    new_metrics = FinancialMetrics(
        id=metrics_id_seq,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        **metrics.model_dump()
    )
    financial_metrics_db.append(new_metrics)
    metrics_id_seq += 1
    return new_metrics

@router.put("/{metrics_id}", response_model=FinancialMetrics)
def update_financial_metrics(metrics_id: int, metrics: FinancialMetricsUpdate):
    for idx, m in enumerate(financial_metrics_db):
        if m.id == metrics_id:
            # Uniqueness validation (excluding the metrics being updated)
            # For updates, we keep the existing company_id, period_end, and period_type
            if not is_unique_metrics(
                m.company_id, 
                m.period_end, 
                m.period_type, 
                exclude_id=metrics_id
            ):
                raise HTTPException(
                    status_code=400, 
                    detail="Financial metrics for this company, period end, and period type must be unique"
                )
            updated = m.copy(update=metrics.model_dump(exclude_unset=True))
            updated.updated_at = datetime.now(timezone.utc)
            financial_metrics_db[idx] = updated
            return updated
    raise HTTPException(status_code=404, detail="Financial metrics not found")

@router.delete("/{metrics_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_financial_metrics(metrics_id: int):
    for idx, m in enumerate(financial_metrics_db):
        if m.id == metrics_id:
            del financial_metrics_db[idx]
            return
    raise HTTPException(status_code=404, detail="Financial metrics not found") 