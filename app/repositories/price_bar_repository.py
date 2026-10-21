"""Read and write stored price bars.

A bar is identified by the instrument, the session date, and the
source. Inserting the same three again updates that row. It does
not add a second one. That is what makes a collector refresh safe
to run twice.
"""

import logging
from datetime import date
from typing import List, Optional

from sqlalchemy.exc import IntegrityError, StatementError
from sqlalchemy.orm import Session

from app.models.database_models import PriceBarDB
from app.models.price_amount import UnreadablePrice
from app.models.price_bar import PriceBarCreate, price_to_json

logger = logging.getLogger(__name__)

_ALREADY_STORED = (
    "A price bar for this instrument, date, and source already exists"
)
# A check constraint, a foreign key, or any other failure that is
# not a duplicate key. The driver text is not included.
_CONSTRAINT = "Price bar could not be stored"
# One skip warning per bar id for this process. Reading the series
# again must not repeat the same line.
_logged_skip_ids = set()


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
        list is still one series. When ``source`` is omitted, that
        series is chosen from every bar of this instrument, including
        bars outside ``start`` and ``end``. The chosen source is the
        one on the bar with the latest ``retrieved_at``. If two
        sources share that time, the source name that sorts last in
        code-point order is kept. That order does not follow the
        database collation. The date window is applied only after
        that choice, so asking for a different range cannot switch
        the series. A
        window that contains none of the chosen source's bars is an
        empty list, even when another source has bars there. Pass
        ``source`` to read one named series, including an empty
        result.
        """
        # The source decision sees the whole instrument. Filtering by
        # date first would let one window pick "fake" and another
        # pick the demo marker.
        bars = self.db.query(PriceBarDB).filter(
            PriceBarDB.instrument_id == instrument_id
        )
        if source is None:
            source = self._default_source(bars)
            if source is None:
                return []
        query = bars.filter(PriceBarDB.source == source)
        if start is not None:
            query = query.filter(PriceBarDB.bar_date >= start)
        if end is not None:
            query = query.filter(PriceBarDB.bar_date <= end)
        rows = query.order_by(
            PriceBarDB.bar_date.asc(),
            PriceBarDB.source.asc(),
            PriceBarDB.id.asc(),
        ).all()
        # A cell that is not a decimal must not fail this query.
        # Dropping the row keeps the rest of the series readable.
        return [row for row in rows if _readable(row)]

    @staticmethod
    def _default_source(query) -> Optional[str]:
        """The one source a list uses when the caller did not name one.

        The latest ``retrieved_at`` is chosen in SQL. Sources that
        share that instant are ordered in Python. ``max`` compares
        code points, which matches SQLite's byte order for these
        names. PostgreSQL ``en_US.UTF-8`` can ignore ``[``, so
        ``ORDER BY source`` would let ``[IAC-DEMO-V2]`` beat ``fake``.
        """
        latest = query.order_by(PriceBarDB.retrieved_at.desc()).first()
        if latest is None:
            return None
        tied = query.filter(
            PriceBarDB.retrieved_at == latest.retrieved_at
        ).all()
        return max(row.source for row in tied)

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
        self._flush_check_commit(instrument_id, [bar], [row], [bar])
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
        self._flush_check_commit(instrument_id, inserted, rows, bars)
        return rows

    def _flush_check_commit(
        self,
        instrument_id: int,
        inserted: List[PriceBarCreate],
        rows: List[PriceBarDB],
        bars: List[PriceBarCreate],
    ) -> None:
        """Flush, prove each price round-trips, then commit.

        The check runs in this transaction. A value we cannot return
        as the same price string is rolled back, so a failed write
        leaves no row behind. ``inserted`` is only the bars this call
        added. An update of a row that was already stored is not in
        that list.
        """
        # Keep the driver error in this handler, then raise outside
        # it. A ``raise`` written inside the ``except`` stores that
        # driver error on ``ValueError.__context__``, and the SQL
        # text would travel with the client error.
        # ``IntegrityError`` is a ``StatementError``. It is caught
        # first so a duplicate still uses the duplicate sentence.
        # A ``ValueError`` from the column type is wrapped as
        # ``StatementError`` and carries the SQL. That wrapper is
        # turned into the fixed sentence outside this handler, so
        # ``__context__`` does not keep the driver error.
        integrity_error = None
        statement_error = False
        try:
            self.db.flush()
            self._reload_flushed(rows)
            for row, bar in zip(rows, bars):
                _require_round_trip(row, bar)
            self.db.commit()
        except IntegrityError as error:
            self.db.rollback()
            integrity_error = error
        except StatementError:
            self.db.rollback()
            statement_error = True
        except ValueError:
            self.db.rollback()
            raise
        if statement_error:
            raise ValueError(_CONSTRAINT) from None
        if integrity_error is not None:
            self._raise_after_integrity(instrument_id, inserted)

    def _reload_flushed(self, rows: List[PriceBarDB]) -> None:
        """Load every flushed row back with one ``SELECT``.

        ``Session.refresh`` would run one query per row. The ids are
        read before ``expire``. After that, touching ``row.id`` would
        load the row by itself. The query fills the identity map, so
        the same objects in ``rows`` then hold the stored prices.
        """
        if not rows:
            return
        ids = [row.id for row in rows]
        for row in rows:
            self.db.expire(row)
        self.db.query(PriceBarDB).filter(PriceBarDB.id.in_(ids)).all()

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


def _readable(row: PriceBarDB) -> bool:
    """False when any OHLC cell did not parse as a decimal."""
    prices = (
        row.open_price,
        row.high_price,
        row.low_price,
        row.close_price,
    )
    if any(isinstance(price, UnreadablePrice) for price in prices):
        if row.id not in _logged_skip_ids:
            _logged_skip_ids.add(row.id)
            logger.warning(
                "Skipping price bar id=%s instrument_id=%s: "
                "stored price is not a decimal",
                row.id,
                row.instrument_id,
            )
        return False
    return True


def _require_round_trip(row: PriceBarDB, bar: PriceBarCreate) -> None:
    """The value just flushed must be the price we are about to return.

    Called before commit. A mismatch raises, and the caller rolls the
    transaction back.
    """
    pairs = (
        (row.open_price, bar.open),
        (row.high_price, bar.high),
        (row.low_price, bar.low),
        (row.close_price, bar.close),
    )
    for stored, expected in pairs:
        if not _same_price(stored, expected):
            raise ValueError(_CONSTRAINT)


def _same_price(stored, expected) -> bool:
    if isinstance(stored, UnreadablePrice):
        return False
    if stored is None or expected is None:
        return stored is None and expected is None
    try:
        return price_to_json(stored) == price_to_json(expected)
    except (ValueError, ArithmeticError):
        return False
