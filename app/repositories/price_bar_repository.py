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
# A check constraint, a foreign key, or any other failure that is
# not a duplicate key. The driver text is not included.
_CONSTRAINT = "Price bar could not be stored"


class PriceBarRepository:
    """CRUD and range queries for ``price_bars``."""

    def __init__(self, db: Session):
        self.db = db

    def get_range(
        self,
        instrument_id: int,
        start: Optional[date] = None,
        end: Optional[date] = None,
        source: Optional[str] = None,
    ) -> List[PriceBarDB]:
        """Bars for one instrument, oldest session first.

        ``start`` and ``end`` are inclusive. Omit either side to leave
        that side open. An instrument with no bars returns an empty
        list. This method does not check that the instrument exists.

        The unique key includes ``source``, so one session can be
        stored twice (a seeded bar and a later refresh). The default
        list is still one series. When ``source`` is omitted, the
        source kept is the one with the latest ``retrieved_at`` inside
        the date range. If two sources share that time, the source
        name that sorts last is kept. Pass ``source`` to read one
        named series, including an empty result.
        """
        query = self.db.query(PriceBarDB).filter(
            PriceBarDB.instrument_id == instrument_id
        )
        if start is not None:
            query = query.filter(PriceBarDB.bar_date >= start)
        if end is not None:
            query = query.filter(PriceBarDB.bar_date <= end)
        if source is None:
            source = self._default_source(query)
            if source is None:
                return []
        query = query.filter(PriceBarDB.source == source)
        return query.order_by(
            PriceBarDB.bar_date.asc(),
            PriceBarDB.source.asc(),
            PriceBarDB.id.asc(),
        ).all()

    @staticmethod
    def _default_source(query) -> Optional[str]:
        """The one source a list uses when the caller did not name one."""
        row = query.order_by(
            PriceBarDB.retrieved_at.desc(),
            PriceBarDB.source.desc(),
        ).first()
        if row is None:
            return None
        return row.source

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
        # Keep the driver error in this handler, then raise outside
        # it. A ``raise`` written inside the ``except`` stores that
        # driver error on ``ValueError.__context__``, and the SQL
        # text would travel with the client error.
        integrity_error = None
        try:
            self.db.commit()
        except IntegrityError as error:
            self.db.rollback()
            integrity_error = error
        if integrity_error is not None:
            self._raise_after_integrity(instrument_id, [bar])
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
        inserted: List[PriceBarCreate] = []
        for bar in bars:
            existing = self.get_by_key(instrument_id, bar.date, bar.source)
            if existing is None:
                existing = self._new_row(instrument_id, bar)
                self.db.add(existing)
                inserted.append(bar)
            else:
                self._copy_onto(existing, bar)
            rows.append(existing)
        # Same as create: raise after the handler so ``__context__``
        # does not keep the driver error.
        integrity_error = None
        try:
            self.db.commit()
        except IntegrityError as error:
            self.db.rollback()
            integrity_error = error
        if integrity_error is not None:
            self._raise_after_integrity(instrument_id, inserted)
        for row in rows:
            self.db.refresh(row)
        return rows

    def _raise_after_integrity(
        self, instrument_id: int, bars: List[PriceBarCreate]
    ) -> None:
        """Turn a failed commit into a client error, outside the handler.

        Call this only after ``rollback``. A duplicate race leaves the
        other transaction's row in place, so ``get_by_key`` finds it
        and the message is the duplicate sentence. A check constraint
        or a foreign key rolls the new row back and leaves no row, so
        the message is generic and does not quote the driver.
        ``bars`` are the keys this call tried to insert. An update of
        a row that was already stored is not in that list: that row
        still exists after rollback, and it is not a duplicate insert.
        """
        for bar in bars:
            stored = self.get_by_key(instrument_id, bar.date, bar.source)
            if stored is not None:
                raise ValueError(_ALREADY_STORED) from None
        raise ValueError(_CONSTRAINT) from None

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
