from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from typing import List, Optional
from app.models.database_models import FinancialMetricsDB
from app.models.financial_metrics import FinancialMetricsCreate, FinancialMetricsUpdate
from datetime import datetime, timezone

class FinancialMetricsRepository:
    """
    Repository class for financial metrics database operations.
    Handles CRUD operations for financial performance data.
    """
    
    def __init__(self, db: Session):
        self.db = db
    
    def create(self, metrics: FinancialMetricsCreate) -> FinancialMetricsDB:
        """
        Create new financial metrics in the database.
        
        Args:
            metrics: FinancialMetricsCreate model with metrics data
            
        Returns:
            FinancialMetricsDB: The created metrics with database-generated fields
            
        Raises:
            ValueError: If metrics for this company/period already exist
        """
        # Check uniqueness before creating
        if not self.is_unique(metrics.company_id, metrics.period_end, metrics.period_type):
            raise ValueError("Financial metrics for this company, period end, and period type must be unique")
        
        # Create new FinancialMetricsDB instance
        db_metrics = FinancialMetricsDB(
            company_id=metrics.company_id,
            period_end=metrics.period_end,
            period_type=metrics.period_type,
            revenue=metrics.revenue,
            net_income=metrics.net_income,
            total_assets=metrics.total_assets,
            total_liabilities=metrics.total_liabilities,
            total_equity=metrics.total_equity,
            roe=metrics.roe,
            roa=metrics.roa,
            gross_margin=metrics.gross_margin,
            net_margin=metrics.net_margin,
            current_ratio=metrics.current_ratio,
            quick_ratio=metrics.quick_ratio,
            debt_to_equity=metrics.debt_to_equity,
            debt_to_assets=metrics.debt_to_assets,
            asset_turnover=metrics.asset_turnover,
            inventory_turnover=metrics.inventory_turnover,
            revenue_growth=metrics.revenue_growth,
            net_income_growth=metrics.net_income_growth,
            pe_ratio=metrics.pe_ratio,
            pb_ratio=metrics.pb_ratio,
            ev_ebitda=metrics.ev_ebitda
        )
        
        # Add to database session
        self.db.add(db_metrics)
        
        try:
            # Commit the transaction
            self.db.commit()
            # Refresh to get database-generated values
            self.db.refresh(db_metrics)
            return db_metrics
        except IntegrityError as e:
            # Rollback on error
            self.db.rollback()
            raise ValueError("Failed to create financial metrics")
    
    def get_by_id(self, metrics_id: int) -> Optional[FinancialMetricsDB]:
        """
        Retrieve financial metrics by ID.
        
        Args:
            metrics_id: The unique identifier of the metrics
            
        Returns:
            FinancialMetricsDB or None: The metrics if found, None otherwise
        """
        return self.db.query(FinancialMetricsDB).filter(FinancialMetricsDB.id == metrics_id).first()
    
    def get_by_company(self, company_id: int, skip: int = 0, limit: int = 100) -> List[FinancialMetricsDB]:
        """
        Retrieve all financial metrics for a specific company.
        
        Args:
            company_id: The ID of the company
            skip: Number of records to skip (for pagination)
            limit: Maximum number of records to return
            
        Returns:
            List[FinancialMetricsDB]: List of financial metrics for the company
        """
        return self.db.query(FinancialMetricsDB).filter(
            FinancialMetricsDB.company_id == company_id
        ).order_by(FinancialMetricsDB.period_end.desc()).offset(skip).limit(limit).all()
    
    def get_all(self, skip: int = 0, limit: int = 100) -> List[FinancialMetricsDB]:
        """
        Retrieve all financial metrics with pagination.
        
        Args:
            skip: Number of records to skip (for pagination)
            limit: Maximum number of records to return
            
        Returns:
            List[FinancialMetricsDB]: List of financial metrics
        """
        return self.db.query(FinancialMetricsDB).offset(skip).limit(limit).all()
    
    def update(self, metrics_id: int, metrics_update: FinancialMetricsUpdate) -> Optional[FinancialMetricsDB]:
        """
        Update existing financial metrics.
        
        Args:
            metrics_id: The ID of the metrics to update
            metrics_update: FinancialMetricsUpdate model with fields to update
            
        Returns:
            FinancialMetricsDB or None: The updated metrics if found, None otherwise
        """
        # Get existing metrics
        db_metrics = self.get_by_id(metrics_id)
        if not db_metrics:
            return None
        
        # Update only the fields that were provided
        update_data = metrics_update.model_dump(exclude_unset=True)
        
        # Update fields
        for field, value in update_data.items():
            setattr(db_metrics, field, value)
        
        # Update timestamp
        db_metrics.updated_at = datetime.now(timezone.utc)
        
        try:
            self.db.commit()
            self.db.refresh(db_metrics)
            return db_metrics
        except IntegrityError as e:
            self.db.rollback()
            raise ValueError("Update failed due to constraint violation")
    
    def delete(self, metrics_id: int) -> bool:
        """
        Delete financial metrics by ID.
        
        Args:
            metrics_id: The ID of the metrics to delete
            
        Returns:
            bool: True if metrics were deleted, False if not found
        """
        db_metrics = self.get_by_id(metrics_id)
        if not db_metrics:
            return False
        
        # Delete the metrics
        self.db.delete(db_metrics)
        self.db.commit()
        return True
    
    def is_unique(self, company_id: int, period_end: datetime, period_type: str, exclude_id: Optional[int] = None) -> bool:
        """
        Check if financial metrics for this company/period combination are unique.
        
        Args:
            company_id: Company ID to check
            period_end: Period end date to check
            period_type: Period type to check
            exclude_id: Metrics ID to exclude from uniqueness check (for updates)
            
        Returns:
            bool: True if unique, False otherwise
        """
        query = self.db.query(FinancialMetricsDB).filter(
            FinancialMetricsDB.company_id == company_id,
            FinancialMetricsDB.period_end == period_end,
            FinancialMetricsDB.period_type == period_type
        )
        
        if exclude_id:
            query = query.filter(FinancialMetricsDB.id != exclude_id)
        
        return not query.first()
