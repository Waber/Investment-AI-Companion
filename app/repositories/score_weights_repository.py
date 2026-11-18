"""Read and replace the weight set for one instrument type.

The built-in equal weights are version 1 and are not a row. The
first PUT inserts version 2. Each later PUT adds 1 to the stored
version. A computed score is not stored here.
"""

import json

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

    The message is fixed. It does not include driver text. Raised
    after the ``except`` so the driver error is not chained on.
    """

    def __init__(self):
        super().__init__(_SAVE_FAILED)


class ScoreWeightsReadError(RuntimeError):
    """The stored JSON is not a weight set this type can use.

    The message is fixed. It does not include the stored text.
    """

    def __init__(self):
        super().__init__(_UNREADABLE)


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
        """Insert version 2, or add 1 to the stored version.

        ``weights`` is the dict ``parse_weights`` already checked.
        The JSON keeps the component order and the numbers that were
        sent. It does not divide them by their sum.
        """
        encoded = _encode(instrument_type, weights)
        row = self.get(instrument_type)
        if row is None:
            row = ScoreWeightsDB(
                instrument_type=instrument_type,
                version=2,
                weights=encoded,
            )
            self.db.add(row)
        else:
            row.version = row.version + 1
            row.weights = encoded
        failed = False
        try:
            self.db.commit()
        except IntegrityError:
            self.db.rollback()
            failed = True
        if failed:
            raise ScoreWeightsSaveError()
        self.db.refresh(row)
        return row


def _decode(instrument_type, raw):
    try:
        payload = json.loads(raw)
        return parse_weights(instrument_type, {"weights": payload})
    except (WeightValidationError, TypeError, ValueError):
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
