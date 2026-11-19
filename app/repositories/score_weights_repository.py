"""Read and replace the weight set for one instrument type.

The built-in equal weights are version 1 and are not a row. The
first PUT inserts version 2. Each later PUT adds 1 to the stored
version. A computed score is not stored here.
"""

import json
from dataclasses import dataclass

from sqlalchemy.exc import IntegrityError

from app.models.database_models import ScoreWeightsDB
from app.scoring import (
    WeightValidationError,
    component_names,
    default_weights,
    parse_weights,
)

_SAVE_FAILED = "Score weights could not be saved"
_UNREADABLE = "Score weights could not be read"


class ScoreWeightsSaveError(RuntimeError):
    """The commit failed and the session was rolled back.

    The message is fixed. It does not include driver text. It is
    raised after the retry loop, outside the ``except`` block, so
    neither ``__cause__`` nor ``__context__`` holds the driver error,
    whose text can include the INSERT and the submitted weights.
    """

    def __init__(self):
        super().__init__(_SAVE_FAILED)


class ScoreWeightsReadError(RuntimeError):
    """The stored JSON is not a weight set this type can use.

    The message is fixed. It does not include the stored text.
    """

    def __init__(self):
        super().__init__(_UNREADABLE)


@dataclass(frozen=True)
class SavedWeights:
    """What one ``save`` wrote: its version and its weights.

    Read inside the write's own transaction, before the commit, so a
    second save that commits right after cannot change it.
    """

    version: int
    weights: dict


class ScoreWeightsRepository:
    """One current weight row per instrument type, or the built-in set."""

    def __init__(self, db):
        self.db = db

    def get(self, instrument_type):
        """The stored row, or None when this type still uses the default."""
        return (
            self.db.query(ScoreWeightsDB)
            .filter(ScoreWeightsDB.instrument_type == instrument_type)
            .first()
        )

    def load(self, instrument_type):
        """``(weights, version, stored)``.

        ``weights`` is a dict of ``Decimal``. ``stored`` is False when
        the row is missing. A row whose text is not the JSON object
        this type expects raises ``ScoreWeightsReadError``.
        """
        row = self.get(instrument_type)
        if row is None:
            return default_weights(instrument_type), 1, False
        weights = _decode(instrument_type, row.weights)
        return weights, row.version, True

    def save(self, instrument_type, weights):
        """Insert version 2, or add 1 to the version stored in the table.

        ``weights`` is the dict ``parse_weights`` already checked.
        The JSON keeps the component order and the numbers that were
        sent. It does not divide them by their sum. The answer is a
        ``SavedWeights`` with the version and the weights this call
        wrote and committed.

        Two callers can both see an empty table. The second insert
        hits the unique type. That attempt is rolled back and tried
        once more, which then updates the row the first caller stored.
        A second conflict is ``ScoreWeightsSaveError``, and the session
        is rolled back. The message does not include driver text.
        """
        encoded = _encode(instrument_type, weights)
        for _attempt in (1, 2):
            try:
                return self._write(instrument_type, encoded)
            except IntegrityError:
                self.db.rollback()
        raise ScoreWeightsSaveError()

    def _write(self, instrument_type, encoded):
        row = self.get(instrument_type)
        if row is None:
            row = ScoreWeightsDB(
                instrument_type=instrument_type,
                version=2,
                weights=encoded,
            )
            self.db.add(row)
        else:
            # The SQL adds 1 to the stored version. Using the number
            # already loaded in this session would ignore a commit
            # that landed after that load.
            row.version = ScoreWeightsDB.version + 1
            row.weights = encoded
        # Flush, then read the version back inside this transaction.
        # A refresh after the commit would start a new transaction,
        # and a second PUT could commit in between: this caller would
        # then report that caller's version and weights as its own.
        # The row stays locked for writes until this commit.
        self.db.flush()
        self.db.refresh(row)
        saved = SavedWeights(
            version=row.version,
            weights=_decode(instrument_type, row.weights),
        )
        self.db.commit()
        return saved


def _decode(instrument_type, raw):
    try:
        payload = json.loads(raw)
        return parse_weights(instrument_type, {"weights": payload})
    except (WeightValidationError, TypeError, ValueError, RecursionError):
        raise ScoreWeightsReadError() from None


def _encode(instrument_type, weights):
    payload = {}
    for name in component_names(instrument_type):
        number = weights[name]
        if number == int(number):
            payload[name] = int(number)
        else:
            payload[name] = float(number)
    return json.dumps(payload)
