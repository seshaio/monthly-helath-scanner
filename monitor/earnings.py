"""
The earnings calendar and the staleness gate.

Most of this universe closes its books in March and December. A run that
lands days before results reviews a name on figures about to be superseded —
noise dressed as a verdict — so anything reporting within the defer window
shows WAIT instead of a score.

Dates come from the feed's calendar and are cached for a day. A missing date
never blocks a verdict: the gate exists to prevent a known-stale review, not
to hold every name hostage to the calendar's coverage.
"""

import sys
from datetime import date

import yfinance as yf

import common
import config


def fetch_dates(codes):
    """Next earnings date per code, cached same-day. None where unknown."""
    cached = common.cache_get("earnings_dates",
                              ttl_hours=config.PRICE_CACHE_TTL_HOURS)
    if cached and set(codes) <= set(cached):
        return cached

    out = dict(cached or {})
    throttle = common.Throttle(config.REQUEST_DELAY_SECONDS)
    for code in codes:
        if code in out:
            continue
        throttle.wait()
        try:
            calendar = yf.Ticker(common.yahoo_symbol(code)).calendar or {}
            dates = calendar.get("Earnings Date") or []
            out[code] = min(dates).isoformat() if dates else None
        except Exception:                            # noqa: BLE001 - optional
            out[code] = None
    common.cache_put("earnings_dates", out)
    return out


def build(rows, today=None):
    """Attach next earnings date and days-to for every equity."""
    today = today or date.today()
    codes = [r["code"] for r in rows if r["asset_type"] == "Equity"]
    dates = fetch_dates(codes)

    for row in rows:
        iso = dates.get(row["code"])
        if not iso:
            row["next_earnings"] = None
            row["days_to_earnings"] = None
            continue
        next_date = date.fromisoformat(iso)
        row["next_earnings"] = iso
        row["days_to_earnings"] = (next_date - today).days
    return rows


def main(argv=None):
    from monitor import universe as universe_mod
    rows = build(universe_mod.resolve())
    for r in rows:
        if r["asset_type"] != "Equity":
            continue
        days = r.get("days_to_earnings")
        print(f"{r['code']:<6} {universe_mod.display_name(r)[:40]:<40} "
              f"{r.get('next_earnings') or 'unknown':<12} "
              f"{f'in {days}d' if days is not None else ''}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
