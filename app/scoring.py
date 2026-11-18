"""Turn stored figures into one 0–100 score.

This module does not read the database, the clock, or a market-data
provider. The caller hands in the numbers, where they came from, the
date they describe, the weight set, and the date the score is for.

A component with nothing usable is ``no data``. It is left out, and
the other weights are divided by their new total so they still add
up to 1. When every component is left out, the total is ``None``
and the status is ``no_score``. That is not a score of zero. A real
zero is status ``scored`` and total ``0.00``.

The scales and the day counts are the rules in ``docs/scoring.md``.
"""

import math
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_FLOOR, ROUND_HALF_UP, Decimal

# A statement can be a year old and still be the latest filing.
STATEMENT_FRESH_DAYS = 548
# One-year volatility and drawdown describe a year of weekly closes.
# A missed week is not stale. 92 days is about a quarter, the same
# length the watchlist uses for a trend window. The 7-day watchlist
# rule is for the latest price, not for this one-year figure.
PRICE_FRESH_DAYS = 92
# TER and fund size are slow facts. One year, including a leap day.
FUND_FRESH_DAYS = 366

_CENT = Decimal("0.01")
_TEN_THOUSANDTH = Decimal("0.0001")
_HUNDRED = Decimal(100)
_WEIGHT_MAX = Decimal("1000000")

STOCK_COMPONENTS = (
    "profitability",
    "valuation",
    "balance_sheet",
    "growth",
)
FUND_COMPONENTS = (
    "cost",
    "size",
    "volatility",
    "max_drawdown",
)
_COMPONENTS = {
    "STOCK": STOCK_COMPONENTS,
    "ETF": FUND_COMPONENTS,
    "ETC": FUND_COMPONENTS,
}


class WeightValidationError(Exception):
    """The weight payload cannot be stored.

    ``code`` is a fixed word. The text of the exception is that same
    word. It does not repeat the value the caller sent.
    """

    def __init__(self, code):
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class _InputSpec:
    """How one stored figure becomes a 0–100 number.

    ``low`` is the end that scores 0. ``high`` is the end that scores
    100. A value past either end stays at 0 or 100. ``kind`` is
    ``linear`` or ``log10``. ``rule`` names the values that are not
    meaningful and must be shown as no data instead of a score.
    """

    name: str
    fresh_days: int
    low: Decimal
    high: Decimal
    kind: str
    rule: str


@dataclass(frozen=True)
class _ComponentSpec:
    name: str
    inputs: tuple


def _specs():
    """The component list for each instrument type, in display order."""
    statement = STATEMENT_FRESH_DAYS
    price = PRICE_FRESH_DAYS
    fund = FUND_FRESH_DAYS
    profitability = _ComponentSpec(
        "profitability",
        (
            _InputSpec(
                "roe", statement, Decimal(0), Decimal("0.20"), "linear", "any"
            ),
            _InputSpec(
                "net_margin",
                statement,
                Decimal(0),
                Decimal("0.20"),
                "linear",
                "any",
            ),
        ),
    )
    valuation = _ComponentSpec(
        "valuation",
        (
            # 10 scores 100. 30 scores 0. Zero or a negative multiple is
            # not "cheap"; it is not a multiple.
            _InputSpec(
                "pe_ratio",
                statement,
                Decimal(30),
                Decimal(10),
                "linear",
                "positive",
            ),
            _InputSpec(
                "pb_ratio",
                statement,
                Decimal(5),
                Decimal(1),
                "linear",
                "positive",
            ),
        ),
    )
    balance_sheet = _ComponentSpec(
        "balance_sheet",
        (
            # Stored like Yahoo's debtToEquity: 45 means 0.45x.
            # 0 scores 100. 200 (2x) scores 0. A negative number is
            # negative equity, which this scale does not describe.
            _InputSpec(
                "debt_to_equity",
                statement,
                Decimal(200),
                Decimal(0),
                "linear",
                "non_negative",
            ),
            _InputSpec(
                "current_ratio",
                statement,
                Decimal("0.5"),
                Decimal(2),
                "linear",
                "non_negative",
            ),
        ),
    )
    growth = _ComponentSpec(
        "growth",
        (
            _InputSpec(
                "revenue_growth",
                statement,
                Decimal("-0.10"),
                Decimal("0.20"),
                "linear",
                "any",
            ),
        ),
    )
    cost = _ComponentSpec(
        "cost",
        (
            _InputSpec(
                "ter",
                fund,
                Decimal("0.01"),
                Decimal(0),
                "linear",
                "non_negative",
            ),
        ),
    )
    size = _ComponentSpec(
        "size",
        (
            # log10(1e7) is 7 and scores 0. log10(1e11) is 11 and scores 100.
            _InputSpec(
                "aum", fund, Decimal(7), Decimal(11), "log10", "positive"
            ),
        ),
    )
    volatility = _ComponentSpec(
        "volatility",
        (
            _InputSpec(
                "volatility",
                price,
                Decimal("0.40"),
                Decimal("0.10"),
                "linear",
                "non_negative",
            ),
        ),
    )
    drawdown = _ComponentSpec(
        "max_drawdown",
        (
            _InputSpec(
                "max_drawdown",
                price,
                Decimal("-0.50"),
                Decimal(0),
                "linear",
                "drawdown",
            ),
        ),
    )
    return {
        "STOCK": (profitability, valuation, balance_sheet, growth),
        "ETF": (cost, size, volatility, drawdown),
        "ETC": (cost, size, volatility, drawdown),
    }


_SPEC_BY_TYPE = _specs()


@dataclass(frozen=True)
class InputScore:
    """One raw figure after the scale is applied, or the reason it was not."""

    name: str
    value: Decimal | None
    normalized: Decimal | None
    status: str
    label: str | None
    source: str | None
    as_of: date | None


@dataclass(frozen=True)
class ComponentScore:
    """One named part of the total.

    ``weight`` is the number that was configured. ``effective_weight``
    is that number divided by the sum of the weights that were used,
    rounded half up to four decimal places. ``contribution`` is what
    this part adds to the total. Excluded parts leave both empty.
    """

    name: str
    status: str
    label: str | None
    normalized: Decimal | None
    weight: Decimal
    effective_weight: Decimal | None
    contribution: Decimal | None
    source: str | None
    as_of: date | None
    inputs: tuple


@dataclass(frozen=True)
class ScoreResult:
    """The whole score for one instrument on one date.

    ``total`` is ``None`` when ``status`` is ``no_score``. ``coverage_label``
    is a short count such as ``3 of 4``. ``oldest_input_date`` is the
    oldest date among the figures that were actually used.
    """

    status: str
    total: Decimal | None
    coverage_available: int
    coverage_total: int
    coverage_label: str
    oldest_input_date: date | None
    components: tuple


def component_names(instrument_type):
    """Component names for this type, in the order the score lists them."""
    names = _COMPONENTS.get(instrument_type)
    if names is None:
        raise WeightValidationError("unknown_type")
    return names


def figure_names(instrument_type):
    """Stored figure names that feed this type, in component order."""
    specs = _SPEC_BY_TYPE.get(instrument_type)
    if specs is None:
        raise WeightValidationError("unknown_type")
    return tuple(item.name for component in specs for item in component.inputs)


def default_weights(instrument_type):
    """Equal weights: the number 1 for every component of this type.

    Scoring divides by the sum, so 1, 1, 1, 1 is the same share as
    0.25 each, without a repeating fraction in the stored numbers.
    """
    names = _COMPONENTS.get(instrument_type)
    if names is None:
        raise WeightValidationError("unknown_type")
    return {name: Decimal(1) for name in names}


def parse_weights(instrument_type, payload):
    """Check a weight document and return ``{component: Decimal}``.

    The document is ``{"weights": {component: number, ...}}`` and it
    must name every component for ``instrument_type`` and no others.
    Each number is finite, from 0 to 1000000 inclusive. Booleans and
    numeric strings are rejected. All zeros are rejected. The stored
    numbers are not divided by their sum here. Scoring does that, and
    it skips a component that has no usable figure.
    """
    if instrument_type not in _COMPONENTS:
        raise WeightValidationError("unknown_type")
    if not isinstance(payload, dict):
        raise WeightValidationError("not_an_object")
    if set(payload) - {"weights"}:
        raise WeightValidationError("unknown_field")
    if "weights" not in payload:
        raise WeightValidationError("missing_weights")
    raw = payload["weights"]
    if not isinstance(raw, dict):
        raise WeightValidationError("weights_not_object")
    names = _COMPONENTS[instrument_type]
    if set(raw) - set(names):
        raise WeightValidationError("unknown_component")
    if set(names) - set(raw):
        raise WeightValidationError("missing_component")
    parsed = {name: _weight_number(raw[name]) for name in names}
    if all(number == 0 for number in parsed.values()):
        raise WeightValidationError("all_zero")
    return parsed


def score_instrument(instrument_type, inputs, weights, on_date):
    """Score one instrument.

    ``inputs`` maps a figure name to ``(value, source, as_of)``.
    A name that is missing is treated as no data. ``weights`` maps
    every component name to a ``Decimal``. ``on_date`` is the day
    the freshness windows are counted back from.
    """
    specs = _SPEC_BY_TYPE.get(instrument_type)
    if specs is None:
        raise WeightValidationError("unknown_type")
    components = tuple(
        _component(spec, inputs, weights.get(spec.name, Decimal(0)), on_date)
        for spec in specs
    )
    used = [
        component for component in components if component.status == "scored"
    ]
    available = len(used)
    total_count = len(components)
    label = f"{available} of {total_count}"
    if not used:
        return ScoreResult(
            status="no_score",
            total=None,
            coverage_available=0,
            coverage_total=total_count,
            coverage_label=label,
            oldest_input_date=None,
            components=components,
        )
    weighted = _with_contributions(components, used)
    oldest = _oldest_used(weighted)
    total = sum(
        component.contribution
        for component in weighted
        if component.contribution is not None
    )
    return ScoreResult(
        status="scored",
        total=_cents(total),
        coverage_available=available,
        coverage_total=total_count,
        coverage_label=label,
        oldest_input_date=oldest,
        components=weighted,
    )


def _weight_number(value):
    """A finite weight in range, or a validation error that names no value."""
    if isinstance(value, bool) or not isinstance(value, (int, float, Decimal)):
        raise WeightValidationError("not_a_number")
    if isinstance(value, float) and not math.isfinite(value):
        raise WeightValidationError("not_a_number")
    number = value if isinstance(value, Decimal) else Decimal(str(value))
    if not number.is_finite():
        raise WeightValidationError("not_a_number")
    if number < 0 or number > _WEIGHT_MAX:
        raise WeightValidationError("out_of_range")
    return number


def _as_decimal(value):
    """A finite number, or None when the figure cannot be scored."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, Decimal):
        number = value
    elif isinstance(value, (int, float)):
        if isinstance(value, float) and not math.isfinite(value):
            return None
        number = Decimal(str(value))
    else:
        return None
    if not number.is_finite():
        return None
    return number


def _meaningful(rule, number):
    if rule == "positive":
        return number > 0
    if rule == "non_negative":
        return number >= 0
    if rule == "drawdown":
        return number <= 0
    return True


def _scale(spec, number):
    """Map ``number`` onto 0–100 using the spec's two ends."""
    measured = number.log10() if spec.kind == "log10" else number
    span = spec.high - spec.low
    raw = (measured - spec.low) / span * _HUNDRED
    if raw < 0:
        return Decimal(0)
    if raw > 100:
        return Decimal(100)
    return raw


def _cents(number):
    return number.quantize(_CENT, rounding=ROUND_HALF_UP)


def _share(number):
    return number.quantize(_TEN_THOUSANDTH, rounding=ROUND_HALF_UP)


def _evaluate_input(spec, raw, on_date):
    value, source, as_of = raw if raw is not None else (None, None, None)
    number = _as_decimal(value)
    kept = number
    if number is None or not _meaningful(spec.rule, number):
        return InputScore(
            name=spec.name,
            value=kept,
            normalized=None,
            status="no_data",
            label="no data",
            source=source,
            as_of=as_of,
        )
    if not isinstance(as_of, date) or (on_date - as_of).days > spec.fresh_days:
        status = "stale" if isinstance(as_of, date) else "no_data"
        return InputScore(
            name=spec.name,
            value=kept,
            normalized=None,
            status=status,
            label="no data",
            source=source,
            as_of=as_of if isinstance(as_of, date) else None,
        )
    return InputScore(
        name=spec.name,
        value=kept,
        normalized=_cents(_scale(spec, number)),
        status="scored",
        label=None,
        source=source,
        as_of=as_of,
    )


def _component(spec, inputs, weight, on_date):
    scored_inputs = tuple(
        _evaluate_input(item, inputs.get(item.name), on_date)
        for item in spec.inputs
    )
    usable = [item for item in scored_inputs if item.status == "scored"]
    weight = weight if isinstance(weight, Decimal) else Decimal(str(weight))
    if not usable:
        return ComponentScore(
            name=spec.name,
            status="no_data",
            label="no data",
            normalized=None,
            weight=weight,
            effective_weight=None,
            contribution=None,
            source=None,
            as_of=None,
            inputs=scored_inputs,
        )
    normalized = _cents(sum(item.normalized for item in usable) / len(usable))
    sources = {item.source for item in usable}
    source = sources.pop() if len(sources) == 1 else None
    as_of = min(item.as_of for item in usable)
    status = "scored" if weight > 0 else "unused"
    return ComponentScore(
        name=spec.name,
        status=status,
        label=None,
        normalized=normalized,
        weight=weight,
        effective_weight=None,
        contribution=None,
        source=source,
        as_of=as_of,
        inputs=scored_inputs,
    )


def _with_contributions(components, used):
    """Fill contribution and effective weight for the parts that count.

    Each contribution is the share times the component score. The
    published cents are the largest-remainder split of that sum, so
    they add up to the rounded total and none of them is negative.
    """
    weight_sum = sum(component.weight for component in used)
    unrounded = []
    shares = []
    for component in used:
        share = component.weight / weight_sum
        shares.append(share)
        unrounded.append(share * component.normalized)
    rounded = _largest_remainder(unrounded)
    by_name = {}
    for component, share, contribution in zip(used, shares, rounded):
        by_name[component.name] = ComponentScore(
            name=component.name,
            status=component.status,
            label=component.label,
            normalized=component.normalized,
            weight=component.weight,
            effective_weight=_share(share),
            contribution=contribution,
            source=component.source,
            as_of=component.as_of,
            inputs=component.inputs,
        )
    return tuple(
        by_name.get(component.name, component) for component in components
    )


def _largest_remainder(unrounded):
    """Split the rounded total into contributions that are never negative.

    Each unrounded contribution is cut down to a whole cent. The cents
    that are left, so the pieces add up to the rounded total, go to the
    largest discarded fractions. A tie goes to the earlier component.
    Giving the whole difference to the last component can make that
    contribution negative.
    """
    target = _cents(sum(unrounded, Decimal(0)))
    cents = [number * 100 for number in unrounded]
    floors = [
        int(item.to_integral_value(rounding=ROUND_FLOOR)) for item in cents
    ]
    leftover = int(target * 100) - sum(floors)
    order = sorted(
        range(len(floors)),
        key=lambda index: (-(cents[index] - floors[index]), index),
    )
    given = list(floors)
    for step in range(max(leftover, 0)):
        given[order[step]] += 1
    return [(Decimal(item) / Decimal(100)) for item in given]


def _oldest_used(components):
    dates = [
        item.as_of
        for component in components
        if component.status == "scored"
        for item in component.inputs
        if item.status == "scored" and item.as_of is not None
    ]
    if not dates:
        return None
    return min(dates)
