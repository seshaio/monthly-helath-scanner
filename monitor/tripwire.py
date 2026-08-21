"""
The weekly tripwire: what watches between monthly runs.

Monthly cadence means up to 30 days blind. This is the cheap check that runs
weekly — price outside the last run's limit band, RSI at an extreme, earnings
inside the defer window, or a fresh break in a price series. Silent when
nothing fired; exit code 1 and a printed list when something did, so cron or
a launchd job can mail the output.

    python -m monitor.tripwire

It is a smoke alarm, not a verdict: it never scores, never advises, only
points at what moved. The monthly run is for thinking.
"""

import os
import sys

import pandas as pd
import yfinance as yf

import common
import config
from monitor import earnings as earnings_mod
from monitor import indicators as indicators_mod
from monitor import universe as universe_mod

RSI_HIGH = 80.0
RSI_LOW = 20.0
EARNINGS_HEADS_UP_DAYS = 7


def check(saved_rows, close_frame, days_to_earnings):
    """Pure logic: compare fresh prices against the last run's snapshot."""
    fired = []
    for row in saved_rows:
        code = row["code"]
        symbol = common.yahoo_symbol(code)
        series = (close_frame[symbol].dropna()
                  if symbol in close_frame.columns else pd.Series(dtype=float))
        if series.empty:
            fired.append((code, "no price returned — check the feed"))
            continue
        price = float(series.iloc[-1])

        breaks = indicators_mod.detect_breaks(series.tail(30))
        if breaks:
            fired.append((code, f"price break: {breaks[0]['looks_like']} "
                                f"on {breaks[0]['date']}"))
            continue

        buy, sell = row.get("buy_limit_1m"), row.get("sell_limit_1m")
        if buy and price < buy:
            fired.append((code, f"below the monthly band: {price:,.0f} < "
                                f"buy limit {buy:,.0f}"))
        elif sell and price > sell:
            fired.append((code, f"above the monthly band: {price:,.0f} > "
                                f"sell limit {sell:,.0f}"))

        rsi = indicators_mod.wilder_rsi(series)
        if not pd.isna(rsi):
            if rsi >= RSI_HIGH:
                fired.append((code, f"RSI {rsi:.0f} — extreme overbought"))
            elif rsi <= RSI_LOW:
                fired.append((code, f"RSI {rsi:.0f} — extreme oversold"))

        days = days_to_earnings.get(code)
        if days is not None and 0 <= days <= EARNINGS_HEADS_UP_DAYS:
            fired.append((code, f"reports in {days} day(s)"))
    return fired


def main(argv=None):
    run_dir = common.latest_run()
    if not run_dir:
        raise SystemExit("no monthly run to compare against — run the report first")
    saved = common.load_json(os.path.join(run_dir, "indicators.json"))

    symbols = [common.yahoo_symbol(r["code"]) for r in saved]
    frame = common.with_retry(lambda: yf.download(
        symbols, period="6mo", interval="1d", auto_adjust=True,
        progress=False, threads=False, group_by="column"))
    if frame is None or frame.empty:
        raise common.DataFeedError("tripwire price fetch returned nothing")
    close = frame["Close"] if "Close" in frame.columns.get_level_values(0) else frame

    rows = earnings_mod.build(universe_mod.load_config())
    days = {r["code"]: r.get("days_to_earnings") for r in rows}

    fired = check(saved, close, days)
    if not fired:
        print("tripwire: quiet")
        return 0
    print(f"tripwire: {len(fired)} alert(s) vs {os.path.basename(run_dir)}\n")
    for code, message in fired:
        print(f"  {code:<6} {message}")
    print("\nnot a verdict — run the monthly report if any of these matter")
    return 1


if __name__ == "__main__":
    sys.exit(main())
