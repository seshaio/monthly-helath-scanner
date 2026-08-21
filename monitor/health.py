"""
The business health ladder.

Binary FINE/BROKEN never fires until it is far too late, because businesses
degrade gradually and nothing reads as broken while there is still a story to
tell about it. So health is graded, and every step is tied to something
observable in the statements.

Thresholds are fixed in config.py before any data is fetched. That is the
whole point: a trigger chosen after seeing the number it fires on is not a
measurement. A trigger can be argued with in the write-up. It cannot be
un-fired.

Two things this deliberately cannot do:

  * Severe events — restatements, auditor changes, going-concern doubt —
    live in filings, not in a price feed. They are declared by hand in
    universe.toml, verified against the issuer, exactly like a corporate
    action.
  * BROKEN is never inferred. Calling a business structurally broken is a
    judgement a human makes on purpose, so it takes its own declaration.
"""

import sys

import numpy as np
import pandas as pd

import common
import config
from monitor import universe as universe_mod
from monitor import valuation as valuation_mod


def _yoy(series):
    """Latest and prior annual values, or (None, None) if there is no prior."""
    series = series.dropna().sort_index()
    if len(series) < config.HEALTH_MIN_PERIODS:
        return None, None
    return float(series.iloc[-1]), float(series.iloc[-2])


def _margin_series(fundamentals):
    revenue = fundamentals["revenue"].dropna()
    operating = fundamentals["operating_income"].dropna()
    shared = revenue.index.intersection(operating.index)
    if shared.empty:
        return pd.Series(dtype=float)
    return (operating[shared] / revenue[shared] * 100).sort_index()


def evaluate_triggers(fundamentals, *, financial=False):
    """
    Test every computable trigger. Returns (fired, unavailable).

    A trigger that cannot be tested is recorded as untested, never as passed.
    Silence from a missing field must not read as a clean bill of health.
    """
    fired, unavailable = [], []

    def unavailable_because(name, why):
        unavailable.append({"trigger": name, "reason": why})

    def fire(name, detail, value, threshold):
        """
        Record a fired trigger, noting how far past the line it actually is.

        A trigger that clears its threshold by a hair produces the same
        verdict as one that clears it by a mile, and the report should not
        present those as the same finding.
        """
        margin = (abs(value - threshold) / abs(threshold) * 100
                  if threshold else 100.0)
        fired.append({
            "trigger": name, "detail": detail, "value": value,
            "threshold": threshold, "margin_pct": margin,
            "marginal": margin <= config.HEALTH_MARGINAL_BAND_PCT,
        })

    # 1. Operating margin, year over year.
    margins = _margin_series(fundamentals)
    latest, prior = _yoy(margins)
    if latest is None:
        unavailable_because("operating_margin_drop_bp", "no comparable periods")
    else:
        drop_bp = (prior - latest) * 100
        threshold = config.HEALTH_TRIGGERS["operating_margin_drop_bp"]
        if drop_bp >= threshold:
            fire("operating_margin_drop_bp",
                 f"operating margin {latest:.1f}% vs {prior:.1f}% a year "
                 f"earlier ({drop_bp:.0f}bp fall)", drop_bp, threshold)

    # 2. Revenue direction.
    latest, prior = _yoy(fundamentals["revenue"])
    if latest is None:
        unavailable_because("revenue_decline_pct", "no comparable periods")
    elif prior:
        change = (latest / prior - 1) * 100
        threshold = config.HEALTH_TRIGGERS["revenue_decline_pct"]
        if change <= threshold:
            fire("revenue_decline_pct",
                 f"revenue {change:+.1f}% year over year", change, threshold)

    # 3. Free cash flow, consecutive negative years.
    fcf = fundamentals["fcf"].dropna().sort_index()
    need = config.HEALTH_TRIGGERS["fcf_negative_consecutive_years"]
    if len(fcf) < need:
        unavailable_because("fcf_negative_consecutive_years", "too few periods")
    else:
        recent = fcf.iloc[-need:]
        if (recent < 0).all():
            # Not a threshold you can be near — it either happened or it did not.
            fired.append({
                "trigger": "fcf_negative_consecutive_years",
                "detail": f"free cash flow negative {need} years running",
                "marginal": False, "margin_pct": 100.0,
            })

    # 4. Leverage. Skipped for financials, where borrowing is raw material.
    if financial:
        unavailable_because("net_debt_to_ebitda_above",
                            "not meaningful for a financial")
    else:
        debt, _ = _yoy(fundamentals["debt"])
        ebitda, _ = _yoy(fundamentals["ebitda"])
        cash = fundamentals["cash_eq"].dropna()
        cash_latest = float(cash.iloc[-1]) if not cash.empty else 0.0
        if debt is None or ebitda is None or ebitda <= 0:
            unavailable_because("net_debt_to_ebitda_above",
                                "debt or EBITDA not reported")
        else:
            # Net cash floors at zero: a cash-rich balance sheet is not a
            # distressed one wearing a minus sign.
            net_debt = max(0.0, debt - cash_latest)
            ratio = net_debt / ebitda
            threshold = config.HEALTH_TRIGGERS["net_debt_to_ebitda_above"]
            if ratio > threshold:
                fire("net_debt_to_ebitda_above",
                     f"net debt / EBITDA {ratio:.2f}x", ratio, threshold)

    # 5. Return on equity.
    income, _ = _yoy(fundamentals["net_income"])
    equity, _ = _yoy(fundamentals["equity"])
    if income is None or equity is None or equity <= 0:
        unavailable_because("roe_below_pct", "net income or equity not reported")
    else:
        roe = income / equity * 100
        threshold = config.HEALTH_TRIGGERS["roe_below_pct"]
        if roe < threshold:
            fire("roe_below_pct", f"return on equity {roe:.1f}%", roe, threshold)

    return fired, unavailable


def assess(code, fundamentals, declared=None):
    """Fired triggers plus declared events, resolved onto the ladder."""
    financial = valuation_mod.is_financial(fundamentals, code)
    fired, unavailable = evaluate_triggers(fundamentals, financial=financial)
    declared = declared or []

    severe = [d for d in declared if d["type"] in config.HEALTH_SEVERE_TRIGGERS]
    breaking = [d for d in declared if d["type"] in config.HEALTH_BROKEN_TRIGGERS]

    result = {
        "fired": fired,
        "declared": declared,
        "unavailable": unavailable,
        "is_financial": financial,
        "trigger_count": len(fired) + len(severe) + len(breaking),
    }

    # Too little to judge on is reported as such, never as a clean result.
    # The bug this replaces marked every healthy company "not assessed":
    # zero triggers fired and zero untested satisfied the old condition, so
    # the cleanest balance sheets in the universe scored the same as the ones
    # with no statements at all.
    tested = len(config.HEALTH_TRIGGERS) - len(unavailable)
    result["triggers_tested"] = tested
    if tested < config.HEALTH_MIN_TRIGGERS_TESTED:
        result["status"] = None
        result["label"] = "not assessed — statements unavailable"
        result["health_score"] = None
        return result

    if breaking:
        status = config.HEALTH_BROKEN
    elif severe or len(fired) >= 2:
        status = config.HEALTH_IMPAIRED
    elif len(fired) == 1:
        status = config.HEALTH_WATCH
    else:
        status = config.HEALTH_INTACT

    result["status"] = status
    result["health_score"] = config.HEALTH_SCORE[status]
    result["label"] = status

    # If dropping any single marginal trigger would move the name up a rung,
    # the whole verdict rests on that hundredth of a decimal. Say so.
    marginal = [t for t in fired if t.get("marginal")]
    if marginal and status in (config.HEALTH_WATCH, config.HEALTH_IMPAIRED):
        without = len(fired) - len(marginal)
        softer = (config.HEALTH_INTACT if without == 0
                  else config.HEALTH_WATCH if without == 1
                  else config.HEALTH_IMPAIRED)
        if softer != status:
            result["marginal_trigger"] = {
                "triggers": [t["trigger"] for t in marginal],
                "would_be": softer,
                "detail": "; ".join(
                    f"{t['trigger']} at {t['value']:.2f} vs threshold "
                    f"{t['threshold']:.2f}" for t in marginal),
            }
    return result


def build(rows):
    """Attach a health assessment to every equity row."""
    declarations = universe_mod.concerns()
    throttle = common.Throttle(config.REQUEST_DELAY_SECONDS)

    for row in rows:
        if row["asset_type"] != "Equity":
            continue
        if row.get("data_suspect"):
            row["health"] = {"status": None, "health_score": None,
                             "label": "not assessed — price series unusable"}
            continue
        throttle.wait()
        fundamentals = valuation_mod.fetch_fundamentals(row["code"])
        row["health"] = assess(row["code"], fundamentals,
                               declarations.get(row["code"]))
    return rows


def main(argv=None):
    from monitor import indicators
    rows = build(indicators.build())
    equities = [r for r in rows if r["asset_type"] == "Equity"]

    print(f"{'CODE':<6} {'NAME':<34} {'STATUS':<10} {'SC':>3}  TRIGGERS")
    print("-" * 100)
    for row in equities:
        health = row["health"]
        score = health.get("health_score")
        print(f"{row['code']:<6} {universe_mod.display_name(row)[:34]:<34} "
              f"{str(health.get('label'))[:10]:<10} "
              f"{(str(score) if score is not None else '—'):>3}  "
              f"{len(health.get('fired', []))} fired")
        for trigger in health.get("fired", []):
            print(f"{'':>6} {'':<34} ⚠ {trigger['detail']}")
        for gap in health.get("unavailable", []):
            print(f"{'':>6} {'':<34} · {gap['trigger']} untested: {gap['reason']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
