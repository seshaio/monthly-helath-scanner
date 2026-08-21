"""
The scorecard: were past verdicts any good?

Without this the framework can run for years without anyone knowing whether
it adds value — and it would keep being run either way. Every run saves its
verdicts; once a verdict is old enough, it is graded against what actually
happened, relative to TOPIX.

Grading rules, fixed here rather than argued monthly:

  BUY   hits if the name beat the TOPIX proxy over the horizon
  SELL  hits if it lagged
  TRIM  hits if it lagged (the call was "the price is ahead of itself")
  KEEP and WAIT are not graded — "nothing to do" has no direction to be
        right about

Below SCORECARD_MIN_VERDICTS graded calls the hit rate is reported as
insufficient, not as a number. A rate computed over one quarter is
indistinguishable from chance, and printing it invites believing it.
"""

import os
import re
from datetime import date, timedelta

import common
import config

GRADEABLE = {"BUY", "SELL", "TRIM"}


def _dated_runs():
    base = os.path.abspath(config.OUTPUT_DIR)
    if not os.path.isdir(base):
        return []
    out = []
    for name in sorted(os.listdir(base)):
        match = re.match(r"^(\d{4}-\d{2}-\d{2})-run-\d+$", name)
        path = os.path.join(base, name, "verdicts.json")
        if match and os.path.exists(path):
            out.append((date.fromisoformat(match.group(1)), path))
    return out


def grade(current_prices, benchmark_now, today=None):
    """
    Grade every verdict old enough for at least the shortest horizon.

    current_prices: {code: price}; benchmark_now: TOPIX-proxy level today.
    Only the oldest run per calendar month is graded, so re-runs within a
    day or month are not counted as independent calls.
    """
    today = today or date.today()
    horizons = sorted(config.SCORECARD_HORIZONS_MONTHS)
    results = {h: [] for h in horizons}

    seen_months = set()
    for run_date, path in _dated_runs():
        month = (run_date.year, run_date.month)
        if month in seen_months:
            continue
        seen_months.add(month)

        saved = common.load_json(path)
        benchmark_then = saved.get("_benchmark_level")
        for horizon in horizons:
            if today - run_date < timedelta(days=horizon * 30):
                continue
            for code, record in saved.items():
                if code.startswith("_"):
                    continue
                verdict = record.get("verdict")
                then = record.get("price")
                now = current_prices.get(code)
                if (verdict not in GRADEABLE or not then or not now
                        or not benchmark_then or not benchmark_now):
                    continue
                name_return = now / then - 1
                bench_return = benchmark_now / benchmark_then - 1
                excess = name_return - bench_return
                hit = excess > 0 if verdict == "BUY" else excess < 0
                results[horizon].append({
                    "code": code, "verdict": verdict, "run": str(run_date),
                    "excess_pct": excess * 100, "hit": hit,
                })
    return results


def summarise(results):
    out = {}
    for horizon, graded in results.items():
        if len(graded) < config.SCORECARD_MIN_VERDICTS:
            out[horizon] = {"graded": len(graded), "sufficient": False}
            continue
        hits = sum(1 for g in graded if g["hit"])
        excess = sorted(g["excess_pct"] for g in graded)
        out[horizon] = {
            "graded": len(graded), "sufficient": True,
            "hit_rate": hits / len(graded),
            "median_excess_pct": excess[len(excess) // 2],
        }
    return out
