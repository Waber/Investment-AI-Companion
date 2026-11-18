"""The score is a pure function of stored inputs and a weight set.

No database and no market-data call. The numbers below are worked by
hand from the rules in ``docs/scoring.md``. A missing total is
``None``. A real zero stays zero, with status ``scored``.
"""

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest

from app.scoring import (
    WeightValidationError,
    component_names,
    default_weights,
    figure_names,
    parse_weights,
    score_instrument,
)

ON = date(2026, 9, 30)
# Annual and quarterly facts stay usable for about 18 months.
STATEMENT_FRESH = ON - timedelta(days=548)
STATEMENT_STALE = ON - timedelta(days=549)
# One-year price figures stay fresh for a quarter: 92 days counts.
PRICE_FRESH = ON - timedelta(days=92)
PRICE_STALE = ON - timedelta(days=93)
# A fee or a fund size is a slow fact: 366 days is still fresh.
FUND_FRESH = ON - timedelta(days=366)
FUND_STALE = ON - timedelta(days=367)


def _stock(**overrides):
    """One fresh value for every stock input. Overrides replace them."""
    inputs = {
        "roe": (Decimal("0.10"), "manual", STATEMENT_FRESH),
        "net_margin": (Decimal("0.20"), "manual", STATEMENT_FRESH),
        "pe_ratio": (Decimal("20"), "manual", STATEMENT_FRESH),
        "pb_ratio": (Decimal("3"), "manual", STATEMENT_FRESH),
        "debt_to_equity": (Decimal("100"), "manual", STATEMENT_FRESH),
        "current_ratio": (Decimal("1.25"), "manual", STATEMENT_FRESH),
        "revenue_growth": (Decimal("0.05"), "manual", STATEMENT_FRESH),
    }
    inputs.update(overrides)
    return inputs


def _fund(**overrides):
    inputs = {
        "ter": (Decimal("0"), "demo", FUND_FRESH),
        "aum": (Decimal("1000000000"), "demo", FUND_FRESH),
        "volatility": (Decimal("0.25"), "fake", PRICE_FRESH),
        "max_drawdown": (Decimal("-0.25"), "fake", PRICE_FRESH),
    }
    inputs.update(overrides)
    return inputs


def _by_name(result):
    return {component.name: component for component in result.components}


def _input(component, name):
    return next(item for item in component.inputs if item.name == name)


def test_stock_score_matches_the_hand_calculation():
    """Equal weights. Each component is the mean of its input scores.

    ROE 0.10 is halfway from 0 to 0.20, so 50. Net margin 0.20 is
    the top of that scale, so 100. Profitability is their mean, 75.
    P/E 20 is halfway from 30 (score 0) to 10 (score 100). P/B 3 is
    halfway from 5 to 1. Debt-to-equity 100 is halfway from 200 to 0.
    Current ratio 1.25 is halfway from 0.5 to 2. Revenue growth 0.05
    is halfway from -0.10 to 0.20. Those four components are
    75, 50, 50 and 50. Each weight is 1, so each share is 1/4:
    18.75 + 12.50 + 12.50 + 12.50 = 56.25.
    """
    result = score_instrument("STOCK", _stock(), default_weights("STOCK"), ON)
    assert result.status == "scored"
    assert result.total == Decimal("56.25")
    assert result.coverage_available == 4
    assert result.coverage_total == 4
    assert result.coverage_label == "4 of 4"
    assert result.oldest_input_date == STATEMENT_FRESH
    assert [item.name for item in result.components] == [
        "profitability",
        "valuation",
        "balance_sheet",
        "growth",
    ]
    parts = _by_name(result)
    assert parts["profitability"].normalized == Decimal("75.00")
    assert parts["valuation"].normalized == Decimal("50.00")
    assert parts["balance_sheet"].normalized == Decimal("50.00")
    assert parts["growth"].normalized == Decimal("50.00")
    assert parts["profitability"].contribution == Decimal("18.75")
    assert parts["growth"].contribution == Decimal("12.50")
    assert parts["profitability"].weight == Decimal("1")
    assert parts["profitability"].effective_weight == Decimal("0.2500")
    assert parts["profitability"].source == "manual"
    assert parts["profitability"].as_of == STATEMENT_FRESH
    assert parts["profitability"].label is None
    roe = _input(parts["profitability"], "roe")
    assert roe.value == Decimal("0.10")
    assert roe.normalized == Decimal("50.00")
    assert roe.status == "scored"
    assert roe.source == "manual"
    assert roe.as_of == STATEMENT_FRESH


def test_missing_component_is_dropped_and_the_rest_are_reweighted():
    """Growth has no figure. Its weight is not given to a zero.

    The other three weights are 1, 1 and 1. Profitability is 75 and
    the other two are 50. The unrounded total is 58.333..., which
    rounds half up to 58.33. The last included contribution gives
    up one hundredth so the published numbers add to that total.
    """
    result = score_instrument(
        "STOCK",
        _stock(revenue_growth=(None, None, None)),
        default_weights("STOCK"),
        ON,
    )
    parts = _by_name(result)
    assert result.status == "scored"
    assert result.total == Decimal("58.33")
    assert result.coverage_label == "3 of 4"
    assert parts["growth"].status == "no_data"
    assert parts["growth"].label == "no data"
    assert parts["growth"].normalized is None
    assert parts["growth"].contribution is None
    assert parts["growth"].effective_weight is None
    assert _input(parts["growth"], "revenue_growth").status == "no_data"
    assert _input(parts["growth"], "revenue_growth").label == "no data"
    assert parts["profitability"].contribution == Decimal("25.00")
    assert parts["valuation"].contribution == Decimal("16.67")
    assert parts["balance_sheet"].contribution == Decimal("16.66")
    assert result.oldest_input_date == STATEMENT_FRESH
    published = [
        part.contribution
        for part in result.components
        if part.contribution is not None
    ]
    assert sum(published) == result.total


def test_custom_weights_change_the_total_after_renormalization():
    """Profitability is three times each of the other present weights.

    Growth is missing, so it does not keep its weight. The remaining
    weights are 3, 1 and 1. 75 * 3/5 + 50 * 1/5 + 50 * 1/5 = 65.
    """
    weights = parse_weights(
        "STOCK",
        {
            "weights": {
                "profitability": 3,
                "valuation": 1,
                "balance_sheet": 1,
                "growth": 1,
            }
        },
    )
    custom = score_instrument(
        "STOCK",
        _stock(revenue_growth=(None, None, None)),
        weights,
        ON,
    )
    equal = score_instrument(
        "STOCK",
        _stock(revenue_growth=(None, None, None)),
        default_weights("STOCK"),
        ON,
    )
    assert custom.total == Decimal("65.00")
    assert equal.total == Decimal("58.33")
    assert custom.total != equal.total
    parts = _by_name(custom)
    assert parts["profitability"].weight == Decimal("3")
    assert parts["profitability"].effective_weight == Decimal("0.6000")
    assert parts["profitability"].contribution == Decimal("45.00")


def test_one_stale_input_is_no_data_and_its_partner_still_scores():
    """ROE is too old. Net margin is fresh, so profitability remains."""
    result = score_instrument(
        "STOCK",
        _stock(roe=(Decimal("0.10"), "manual", STATEMENT_STALE)),
        default_weights("STOCK"),
        ON,
    )
    parts = _by_name(result)
    roe = _input(parts["profitability"], "roe")
    assert roe.status == "stale"
    assert roe.label == "no data"
    assert roe.normalized is None
    assert parts["profitability"].normalized == Decimal("100.00")
    assert result.total == Decimal("62.50")
    assert result.oldest_input_date == STATEMENT_FRESH


def test_a_component_whose_inputs_are_all_stale_is_excluded():
    result = score_instrument(
        "STOCK",
        _stock(
            roe=(Decimal("0.10"), "manual", STATEMENT_STALE),
            net_margin=(Decimal("0.20"), "manual", STATEMENT_STALE),
        ),
        default_weights("STOCK"),
        ON,
    )
    parts = _by_name(result)
    assert parts["profitability"].status == "no_data"
    assert parts["profitability"].label == "no data"
    assert result.coverage_label == "3 of 4"
    assert result.total == Decimal("50.00")


def test_freshness_boundaries_keep_the_exact_day():
    """548, 92 and 366 days are fresh. One day older is stale."""
    fresh = score_instrument("STOCK", _stock(), default_weights("STOCK"), ON)
    assert _input(_by_name(fresh)["profitability"], "roe").status == "scored"

    stale_statement = score_instrument(
        "STOCK",
        _stock(
            roe=(Decimal("0.10"), "manual", STATEMENT_STALE),
            net_margin=(Decimal("0.20"), "manual", STATEMENT_STALE),
            pe_ratio=(Decimal("20"), "manual", STATEMENT_STALE),
            pb_ratio=(Decimal("3"), "manual", STATEMENT_STALE),
            debt_to_equity=(Decimal("100"), "manual", STATEMENT_STALE),
            current_ratio=(Decimal("1.25"), "manual", STATEMENT_STALE),
            revenue_growth=(Decimal("0.05"), "manual", STATEMENT_STALE),
        ),
        default_weights("STOCK"),
        ON,
    )
    assert stale_statement.status == "no_score"

    fund = score_instrument(
        "ETF",
        _fund(
            ter=(Decimal("0"), "demo", FUND_FRESH),
            aum=(Decimal("1000000000"), "demo", FUND_STALE),
            volatility=(Decimal("0.25"), "fake", PRICE_FRESH),
            max_drawdown=(Decimal("-0.25"), "fake", PRICE_STALE),
        ),
        default_weights("ETF"),
        ON,
    )
    parts = _by_name(fund)
    assert _input(parts["cost"], "ter").status == "scored"
    assert _input(parts["size"], "aum").status == "stale"
    assert _input(parts["volatility"], "volatility").status == "scored"
    assert _input(parts["max_drawdown"], "max_drawdown").status == "stale"
    assert fund.coverage_label == "2 of 4"


def test_a_future_as_of_date_is_fresh_and_a_missing_date_is_not():
    future = ON + timedelta(days=1)
    result = score_instrument(
        "ETF",
        _fund(
            ter=(Decimal("0"), "demo", future),
            aum=(Decimal("1000000000"), "demo", None),
        ),
        default_weights("ETF"),
        ON,
    )
    parts = _by_name(result)
    assert _input(parts["cost"], "ter").status == "scored"
    assert _input(parts["size"], "aum").status == "no_data"


def test_nothing_usable_is_no_score_rather_than_zero():
    empty = {name: (None, None, None) for name in _stock()}
    result = score_instrument("STOCK", empty, default_weights("STOCK"), ON)
    assert result.status == "no_score"
    assert result.total is None
    assert result.total != Decimal("0")
    assert result.coverage_label == "0 of 4"
    assert result.oldest_input_date is None
    assert all(part.label == "no data" for part in result.components)


def test_a_real_zero_is_a_score():
    """Every scale is at its worst end. The total is zero, not missing."""
    result = score_instrument(
        "STOCK",
        _stock(
            roe=(Decimal("-0.50"), "manual", STATEMENT_FRESH),
            net_margin=(Decimal("-0.50"), "manual", STATEMENT_FRESH),
            pe_ratio=(Decimal("100"), "manual", STATEMENT_FRESH),
            pb_ratio=(Decimal("10"), "manual", STATEMENT_FRESH),
            debt_to_equity=(Decimal("200"), "manual", STATEMENT_FRESH),
            current_ratio=(Decimal("0.10"), "manual", STATEMENT_FRESH),
            revenue_growth=(Decimal("-0.50"), "manual", STATEMENT_FRESH),
        ),
        default_weights("STOCK"),
        ON,
    )
    assert result.status == "scored"
    assert result.total == Decimal("0.00")
    assert result.coverage_label == "4 of 4"


def test_scale_ends_and_values_that_are_not_meaningful():
    """The endpoints score 0 or 100. A ratio that is not a ratio is out."""
    result = score_instrument(
        "STOCK",
        _stock(
            roe=(Decimal("0"), "manual", STATEMENT_FRESH),
            net_margin=(Decimal("0.30"), "manual", STATEMENT_FRESH),
            pe_ratio=(Decimal("-4"), "manual", STATEMENT_FRESH),
            pb_ratio=(Decimal("0"), "manual", STATEMENT_FRESH),
            debt_to_equity=(Decimal("-1"), "manual", STATEMENT_FRESH),
            current_ratio=(Decimal("2"), "manual", STATEMENT_FRESH),
            revenue_growth=(Decimal("0.20"), "manual", STATEMENT_FRESH),
        ),
        default_weights("STOCK"),
        ON,
    )
    parts = _by_name(result)
    assert _input(parts["profitability"], "roe").normalized == Decimal("0.00")
    assert _input(parts["profitability"], "net_margin").normalized == (
        Decimal("100.00")
    )
    assert _input(parts["valuation"], "pe_ratio").status == "no_data"
    assert _input(parts["valuation"], "pb_ratio").status == "no_data"
    assert parts["valuation"].status == "no_data"
    assert _input(parts["balance_sheet"], "debt_to_equity").status == (
        "no_data"
    )
    assert _input(parts["balance_sheet"], "current_ratio").normalized == (
        Decimal("100.00")
    )
    assert _input(parts["growth"], "revenue_growth").normalized == Decimal(
        "100.00"
    )


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("roe", Decimal("NaN")),
        ("net_margin", Decimal("Infinity")),
        ("pe_ratio", True),
        ("current_ratio", "1.5"),
    ],
)
def test_non_numbers_are_no_data(name, value):
    result = score_instrument(
        "STOCK",
        _stock(**{name: (value, "manual", STATEMENT_FRESH)}),
        default_weights("STOCK"),
        ON,
    )
    component = next(
        part
        for part in result.components
        if any(item.name == name for item in part.inputs)
    )
    assert _input(component, name).status == "no_data"


def test_fund_score_and_a_missing_fee():
    """TER 0 is a full cost score. AUM 1e9 is the middle of the log scale.

    Volatility 0.25 and drawdown -0.25 are each halfway. Equal weights
    give 25 + 12.50 + 12.50 + 12.50 = 62.50. An ETC uses the same
    components. A null TER drops cost and the other three fifties
    become 16.67, 16.67 and 16.66.
    """
    weights = default_weights("ETF")
    assert default_weights("ETC") == weights
    full = score_instrument("ETC", _fund(), weights, ON)
    assert full.total == Decimal("62.50")
    assert [item.name for item in full.components] == [
        "cost",
        "size",
        "volatility",
        "max_drawdown",
    ]
    partial = score_instrument(
        "ETF",
        _fund(ter=(None, None, None)),
        weights,
        ON,
    )
    assert partial.coverage_label == "3 of 4"
    assert partial.total == Decimal("50.00")
    parts = _by_name(partial)
    assert parts["cost"].label == "no data"
    assert parts["size"].contribution == Decimal("16.67")
    assert parts["volatility"].contribution == Decimal("16.67")
    assert parts["max_drawdown"].contribution == Decimal("16.66")
    assert (
        sum(
            part.contribution
            for part in partial.components
            if part.contribution is not None
        )
        == partial.total
    )


def test_zero_weight_drops_the_component_even_when_it_has_data():
    weights = parse_weights(
        "ETF",
        {
            "weights": {
                "cost": 0,
                "size": 1,
                "volatility": 1,
                "max_drawdown": 1,
            }
        },
    )
    result = score_instrument("ETF", _fund(), weights, ON)
    parts = _by_name(result)
    assert parts["cost"].status == "unused"
    assert parts["cost"].label is None
    assert parts["cost"].normalized == Decimal("100.00")
    assert parts["cost"].contribution is None
    assert result.coverage_label == "3 of 4"
    assert result.total == Decimal("50.00")


def test_a_zero_weight_and_no_data_left_is_no_score():
    weights = parse_weights(
        "ETF",
        {
            "weights": {
                "cost": 1,
                "size": 0,
                "volatility": 0,
                "max_drawdown": 0,
            }
        },
    )
    result = score_instrument(
        "ETF", _fund(ter=(None, None, None)), weights, ON
    )
    assert result.status == "no_score"
    assert result.total is None


def test_oldest_input_date_ignores_excluded_inputs():
    """The fresh ROE date is kept. The older stale margin is not."""
    result = score_instrument(
        "STOCK",
        _stock(
            roe=(Decimal("0.10"), "manual", STATEMENT_FRESH),
            net_margin=(Decimal("0.20"), "manual", STATEMENT_STALE),
            pe_ratio=(Decimal("20"), "manual", ON),
            pb_ratio=(Decimal("3"), "manual", ON),
            debt_to_equity=(Decimal("100"), "manual", ON),
            current_ratio=(Decimal("1.25"), "manual", ON),
            revenue_growth=(Decimal("0.05"), "manual", ON),
        ),
        default_weights("STOCK"),
        ON,
    )
    assert result.oldest_input_date == STATEMENT_FRESH


def test_two_sources_on_one_component_leave_the_component_source_empty():
    result = score_instrument(
        "STOCK",
        _stock(
            roe=(Decimal("0.10"), "manual", STATEMENT_FRESH),
            net_margin=(Decimal("0.20"), "demo", STATEMENT_FRESH),
        ),
        default_weights("STOCK"),
        ON,
    )
    assert _by_name(result)["profitability"].source is None


def test_unknown_type_is_rejected_before_any_score():
    for caller in (component_names, figure_names, default_weights):
        with pytest.raises(WeightValidationError) as caught:
            caller("BOND")
        assert caught.value.code == "unknown_type"
    with pytest.raises(WeightValidationError) as caught:
        score_instrument("BOND", {}, {}, ON)
    assert caught.value.code == "unknown_type"


def test_a_non_finite_decimal_weight_is_not_a_number():
    with pytest.raises(WeightValidationError) as caught:
        parse_weights(
            "STOCK",
            {
                "weights": {
                    "profitability": Decimal("NaN"),
                    "valuation": 1,
                    "balance_sheet": 1,
                    "growth": 1,
                }
            },
        )
    assert caught.value.code == "not_a_number"


def test_a_non_finite_float_input_is_no_data():
    result = score_instrument(
        "STOCK",
        _stock(roe=(float("nan"), "manual", STATEMENT_FRESH)),
        default_weights("STOCK"),
        ON,
    )
    roe = _input(_by_name(result)["profitability"], "roe")
    assert roe.status == "no_data"
    assert roe.value is None


def test_oldest_date_helper_is_empty_when_no_figure_was_used():
    """The guard returns None. A scored figure always has a date."""
    from app.scoring import ComponentScore, InputScore, _oldest_used

    empty = ComponentScore(
        name="growth",
        status="no_data",
        label="no data",
        normalized=None,
        weight=Decimal(1),
        effective_weight=None,
        contribution=None,
        source=None,
        as_of=None,
        inputs=(
            InputScore(
                name="revenue_growth",
                value=None,
                normalized=None,
                status="no_data",
                label="no data",
                source=None,
                as_of=None,
            ),
        ),
    )
    assert _oldest_used((empty,)) is None


def test_the_score_clock_uses_one_frozen_instant(monkeypatch):
    """One patched instant. A second wall-clock read must not matter.

    Comparing ``utc_today()`` with a later ``datetime.now`` flips the
    date when the two calls fall on either side of midnight.
    """
    from app.api import scores as scores_api

    frozen = datetime(2026, 11, 18, 23, 59, tzinfo=timezone.utc)

    class _Clock:
        @staticmethod
        def now(tz=None):
            return frozen

    monkeypatch.setattr(scores_api, "datetime", _Clock)
    assert scores_api.utc_today() == date(2026, 11, 18)


def test_collector_debt_to_equity_is_a_percent():
    """45.0 is Yahoo's percent for 0.45x, not a multiple of 45.

    The scale is 200 (score 0) to 0 (score 100), the same line as
    2x to 0x. Halfway is 100, which is 1.0x. 45 is
    ``(45 - 200) / (0 - 200) * 100 = 77.5``.
    """
    from app.data_collectors.fake import STOCK_METRICS

    stored = STOCK_METRICS["DEMO_PL_TECH"]["debt_to_equity"]
    assert stored == 45.0
    result = score_instrument(
        "STOCK",
        _stock(
            debt_to_equity=(Decimal(str(stored)), "manual", STATEMENT_FRESH)
        ),
        default_weights("STOCK"),
        ON,
    )
    debt = _input(_by_name(result)["balance_sheet"], "debt_to_equity")
    assert debt.status == "scored"
    assert debt.normalized == Decimal("77.50")


def test_contributions_stay_non_negative_when_cents_do_not_divide():
    """Four tiny scores must not give the last component -0.01.

    Normalized scores 0.02, 0.02, 0.02 and 0.00 with equal weights
    have unrounded contributions 0.005, 0.005, 0.005 and 0. The total
    rounds to 0.02. Largest-remainder gives the extra cents to the
    first ties, and every contribution stays at least zero.
    """
    tiny = Decimal("0.009998")
    calm = Decimal("0.39994")
    # log10 of this amount is 7.0008, which scores 0.02 on the AUM line.
    size = Decimal(10) ** Decimal("7.0008")
    result = score_instrument(
        "ETF",
        _fund(
            ter=(tiny, "demo", FUND_FRESH),
            aum=(size, "demo", FUND_FRESH),
            volatility=(calm, "fake", PRICE_FRESH),
            max_drawdown=(Decimal("-0.50"), "fake", PRICE_FRESH),
        ),
        default_weights("ETF"),
        ON,
    )
    parts = _by_name(result)
    assert parts["cost"].normalized == Decimal("0.02")
    assert parts["size"].normalized == Decimal("0.02")
    assert parts["volatility"].normalized == Decimal("0.02")
    assert parts["max_drawdown"].normalized == Decimal("0.00")
    published = [
        part.contribution
        for part in result.components
        if part.contribution is not None
    ]
    assert all(item >= 0 for item in published)
    assert sum(published) == result.total
    assert result.total == Decimal("0.02")
    assert [part.contribution for part in result.components] == [
        Decimal("0.01"),
        Decimal("0.01"),
        Decimal("0.00"),
        Decimal("0.00"),
    ]


def test_default_weights_are_one_per_component():
    assert default_weights("STOCK") == {
        "profitability": Decimal("1"),
        "valuation": Decimal("1"),
        "balance_sheet": Decimal("1"),
        "growth": Decimal("1"),
    }
    assert set(default_weights("ETF")) == {
        "cost",
        "size",
        "volatility",
        "max_drawdown",
    }


def test_parse_weights_keeps_the_numbers_that_were_sent():
    parsed = parse_weights(
        "STOCK",
        {
            "weights": {
                "profitability": 1,
                "valuation": 1.5,
                "balance_sheet": 0,
                "growth": 1000000,
            }
        },
    )
    assert parsed["valuation"] == Decimal("1.5")
    assert parsed["balance_sheet"] == Decimal("0")
    assert parsed["growth"] == Decimal("1000000")


@pytest.mark.parametrize(
    ("instrument_type", "payload", "code"),
    [
        ("BOND", {"weights": {}}, "unknown_type"),
        ("stock", {"weights": {}}, "unknown_type"),
        ("STOCK", ["profitability"], "not_an_object"),
        ("STOCK", {"weights": {}, "note": 1}, "unknown_field"),
        ("STOCK", {}, "missing_weights"),
        ("STOCK", {"weights": []}, "weights_not_object"),
        (
            "STOCK",
            {
                "weights": {
                    "profitability": 1,
                    "valuation": 1,
                    "balance_sheet": 1,
                    "growth": 1,
                    "buy": 1,
                }
            },
            "unknown_component",
        ),
        (
            "STOCK",
            {"weights": {"profitability": 1}},
            "missing_component",
        ),
        (
            "ETF",
            {
                "weights": {
                    "profitability": 1,
                    "valuation": 1,
                    "balance_sheet": 1,
                    "growth": 1,
                }
            },
            "unknown_component",
        ),
        (
            "STOCK",
            {
                "weights": {
                    "profitability": True,
                    "valuation": 1,
                    "balance_sheet": 1,
                    "growth": 1,
                }
            },
            "not_a_number",
        ),
        (
            "STOCK",
            {
                "weights": {
                    "profitability": "1",
                    "valuation": 1,
                    "balance_sheet": 1,
                    "growth": 1,
                }
            },
            "not_a_number",
        ),
        (
            "STOCK",
            {
                "weights": {
                    "profitability": float("inf"),
                    "valuation": 1,
                    "balance_sheet": 1,
                    "growth": 1,
                }
            },
            "not_a_number",
        ),
        (
            "STOCK",
            {
                "weights": {
                    "profitability": -0.1,
                    "valuation": 1,
                    "balance_sheet": 1,
                    "growth": 1,
                }
            },
            "out_of_range",
        ),
        (
            "STOCK",
            {
                "weights": {
                    "profitability": 1000001,
                    "valuation": 1,
                    "balance_sheet": 1,
                    "growth": 1,
                }
            },
            "out_of_range",
        ),
        (
            "STOCK",
            {
                "weights": {
                    "profitability": 0,
                    "valuation": 0,
                    "balance_sheet": 0,
                    "growth": 0,
                }
            },
            "all_zero",
        ),
    ],
)
def test_weight_payloads_fail_with_a_code_and_not_the_input(
    instrument_type, payload, code
):
    with pytest.raises(WeightValidationError) as caught:
        parse_weights(instrument_type, payload)
    assert caught.value.code == code
    assert "buy" not in str(caught.value)
    assert "driver" not in str(caught.value)


def test_score_strings_do_not_use_advice_words():
    """The result's own text is a score, not an instruction."""
    result = score_instrument(
        "STOCK",
        _stock(revenue_growth=(None, None, None)),
        default_weights("STOCK"),
        ON,
    )
    text = " ".join(
        [
            result.status,
            result.coverage_label,
            *(part.status for part in result.components),
            *(part.label or "" for part in result.components),
            *(
                item.label or ""
                for part in result.components
                for item in part.inputs
            ),
        ]
    )
    folded = text.casefold()
    for word in ("buy", "sell", "hold", "recommendation", "kupuj"):
        assert word not in folded
