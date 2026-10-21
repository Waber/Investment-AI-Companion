"""Read and write stored price bars.

A bar is identified by the instrument, the session date, and the
source. Inserting the same three again updates that row. It does
not add a second one. That is what makes a collector refresh safe
to run twice.
"""

from datetime import date
from typing import List, Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.database_models import PriceBarDB
from app.models.price_bar import PriceBarCreate

_ALREADY_STORED = (
    "A price bar for this instrument, date, and source already exists"
)


class PriceBarRepository:
    """CRUD and range queries for ``price_bars``."""

    def __init__(self, db: Session):
        self.db = db

    def get_range(
        self,
        instrument_id: int,
        start: Optional[date] = None,
        end: Optional[date] = None,
    ) -> List[PriceBarDB]:
        """Bars for one instrument, oldest session first.

        ``start`` and ``end`` are inclusive. Omit either side to leave
        that side open. An instrument with no bars returns an empty
        list. This method does not check that the instrument exists.
        """
        query = self.db.query(PriceBarDB).filter(
            PriceBarDB.instrument_id == instrument_id
        )
        if start is not None:
            query = query.filter(PriceBarDB.bar_date >= start)
        if end is not None:
            query = query.filter(PriceBarDB.bar_date <= end)
        return query.order_by(
            PriceBarDB.bar_date.asc(),
            PriceBarDB.source.asc(),
            PriceBarDB.id.asc(),
        ).all()

    def get_by_key(
        self, instrument_id: int, bar_date: date, source: str
    ) -> Optional[PriceBarDB]:
        """The one row for this instrument, session, and source."""
        return (
            self.db.query(PriceBarDB)
            .filter(
                PriceBarDB.instrument_id == instrument_id,
                PriceBarDB.bar_date == bar_date,
                PriceBarDB.source == source,
            )
            .one_or_none()
        )

    def create(self, instrument_id: int, bar: PriceBarCreate) -> PriceBarDB:
        """Insert one bar. A duplicate key is a ``ValueError``.

        The caller commits one row, matching the financial-metrics
        repository, so a failed seed can resume at the next missing
        bar.
        """
        if self.get_by_key(instrument_id, bar.date, bar.source) is not None:
            raise ValueError(_ALREADY_STORED)
        row = self._new_row(instrument_id, bar)
        self.db.add(row)
        try:
            self.db.commit()
        except IntegrityError:
            self.db.rollback()
            raise ValueError(_ALREADY_STORED)
        self.db.refresh(row)
        return row

    def upsert_many(
        self, instrument_id: int, bars: List[PriceBarCreate]
    ) -> List[PriceBarDB]:
        """Insert or update every bar, then commit once.

        A second call with the same instrument, dates, and source
        changes the stored rows in place. The number of rows for
        that key does not grow. Rows for a different source are
        left alone.
        """
        rows: List[PriceBarDB] = []
        for bar in bars:
            existing = self.get_by_key(instrument_id, bar.date, bar.source)
            if existing is None:
                existing = self._new_row(instrument_id, bar)
                self.db.add(existing)
            else:
                self._copy_onto(existing, bar)
            rows.append(existing)
        try:
            self.db.commit()
        except IntegrityError:
            self.db.rollback()
            raise ValueError(_ALREADY_STORED)
        for row in rows:
            self.db.refresh(row)
        return rows

    @staticmethod
    def _new_row(instrument_id: int, bar: PriceBarCreate) -> PriceBarDB:
        return PriceBarDB(
            instrument_id=instrument_id,
            bar_date=bar.date,
            open_price=bar.open,
            high_price=bar.high,
            low_price=bar.low,
            close_price=bar.close,
            volume=bar.volume,
            currency=bar.currency,
            source=bar.source,
            retrieved_at=bar.retrieved_at,
        )

    @staticmethod
    def _copy_onto(row: PriceBarDB, bar: PriceBarCreate) -> None:
        """Replace the values a refresh is allowed to change.

        The key (instrument, date, source) stays. A later retrieval
        can correct a price or move ``retrieved_at`` forward.
        """
        row.open_price = bar.open
        row.high_price = bar.high
        row.low_price = bar.low
        row.close_price = bar.close
        row.volume = bar.volume
        row.currency = bar.currency
        row.retrieved_at = bar.retrieved_at
