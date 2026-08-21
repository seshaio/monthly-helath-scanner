"""
Price-derived indicators. Every number here is computed, never retrieved.

This is the reason the project exists in this shape. Asking a model for "the
14-day RSI" returns a figure of unknown date and unknown smoothing method that
differs between models, so disagreement between reviewers becomes disagreement
about arithmetic instead of about meaning. Here the arithmetic is settled
before any model sees anything.
"""

import sys

import numpy as np
import pandas as pd
import yfinance as yf

import common
import config
from monitor import universe as universe_mod


def tick_size(price):
    """Valid TSE price increment at this price level."""
    for ceiling, tick in config.TSE_TICK_TABLE:
        if price <= ceiling:
            return tick
    return config.TSE_TICK_TABLE[-1][1]


def round_to_tick(price, *, up):
    """
    Snap a price to the tick grid — down for a buy limit, up for a sell.

    The tick is taken at the candidate price itself, not the last trade: a
    name trading at 5,100 with a buy band at 4,700 ticks in ¥5, not ¥10.
    Rounding conservatively (buy down, sell up) means the printed figure is
    always placeable and never inside the band it claims to mark.
    """
    tick = tick_size(price)
    steps = np.floor(price / tick) if not up else np.ceil(price / tick)
    return float(steps * tick)


def limit_band(price, volatility_1y_pct):
    """
    One-month limit-order band from realised volatility.

    Monthly sigma is the annualised figure over sqrt(12). This is a
    statistical band, not a forecast: it says where a typical month's close
    lands if volatility stays put, and nothing about direction.
    """
    if price is None or volatility_1y_pct is None or np.isnan(volatility_1y_pct):
        return None, None
    sigma_month = volatility_1y_pct / 100 / np.sqrt(12) * config.LIMIT_BAND_SIGMAS
    return (round_to_tick(price * (1 - sigma_month), up=False),
            round_to_tick(price * (1 + sigma_month), up=True))


def wilder_rsi(close, period=None):
    """
    Wilder's RSI — the original 1978 definition, not an EMA approximation.

    Seeded with a simple mean of the first `period` changes, then smoothed
    recursively as avg = (prev * (period - 1) + current) / period. Pandas'
    ewm(adjust=False) is close and converges, but it seeds from the first
    observation rather than the SMA, so it is not the same number early in a
    series. Stating which RSI this is matters more than which one we picked.
    """
    period = period or config.RSI_PERIOD
    close = pd.Series(close).dropna()
    if len(close) < period + 1:
        return np.nan

    delta = close.diff().dropna()
    gains = delta.clip(lower=0).to_numpy(dtype=float)
    losses = (-delta.clip(upper=0)).to_numpy(dtype=float)

    avg_gain = gains[:period].mean()
    avg_loss = losses[:period].mean()
    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period

    if avg_loss == 0:
        if avg_gain == 0:
            # A flat series has no down-days AND no up-days. Reading that as
            # RSI 100 marked a dormant name "extreme overbought" and fired
            # the tripwire on nothing. Flat is no information, not a signal.
            return np.nan
        # No down-days but real gains: 100 is the conventional reading.
        return 100.0
    rs = avg_gain / avg_loss
    return float(100 - 100 / (1 + rs))


def _looks_like_split(ratio):
    """Is this day-over-day ratio close to a common split factor?"""
    for r in config.COMMON_SPLIT_RATIOS:
        for candidate in (r, 1 / r):
            if abs(ratio - candidate) / candidate <= config.SPLIT_RATIO_TOLERANCE:
                return candidate
    return None


def detect_breaks(close):
    """
    Find single-session moves too large to be market events.

    Returns a list of breaks, each naming what it looks like. An empty list
    means the series is usable; anything else means it is not, and the caller
    must refuse to score rather than compute confident nonsense on top of it.
    """
    close = pd.Series(close).dropna()
    if len(close) < 2:
        return []

    breaks = []
    changes = close.pct_change()
    limit = config.MAX_PLAUSIBLE_DAILY_MOVE_PCT / 100
    for date, change in changes[changes.abs() > limit].items():
        i = close.index.get_loc(date)
        before, after = float(close.iloc[i - 1]), float(close.iloc[i])
        ratio = before / after if after else float("inf")
        split = _looks_like_split(ratio)

        # Ratio alone cannot tell a split from a bad print — both look like a
        # clean 10x. What separates them is what the series does next: after a
        # split it stays on the new scale, after a bad print it returns to the
        # old one. Guessing from the ratio alone got 1655 wrong on the first
        # live run, which is why this check exists.
        window = close.iloc[i + 1:i + 1 + config.BREAK_LOOKAHEAD_SESSIONS]
        recovered = False
        if len(window):
            level = float(window.median())
            recovered = abs(level / before - 1) < config.BREAK_RECOVERY_TOLERANCE

        if recovered:
            looks_like = "bad print — series returns to its previous level"
        elif split:
            looks_like = f"unrecorded {split:g}:1 split"
        else:
            looks_like = "unexplained break — verify against the issuer"

        breaks.append({
            "date": date.strftime("%Y-%m-%d"),
            "from": before,
            "to": after,
            "change_pct": float(change * 100),
            "ratio": float(ratio),
            "recovered": recovered,
            "looks_like": looks_like,
        })
    return breaks


def _pct_change_over(close, days):
    """Total return over the last `days` trading sessions, in percent."""
    if len(close) <= days:
        return np.nan
    then, now = close.iloc[-days - 1], close.iloc[-1]
    return float((now / then - 1) * 100) if then else np.nan


def _max_drawdown(close):
    """Worst peak-to-trough fall in the series, in percent (negative)."""
    if close.empty:
        return np.nan
    running_peak = close.cummax()
    return float(((close / running_peak) - 1).min() * 100)


def apply_corrections(close, fixes):
    """
    Apply human-declared corporate actions to a price series.

    A split divides everything strictly before its date by the ratio, putting
    the whole series on today's scale. A bad print drops that one session.
    Every action taken is returned alongside, so the run records what was
    changed rather than presenting repaired data as if it arrived that way.
    """
    close = pd.Series(close).dropna()
    applied = []
    if not fixes:
        return close, applied

    for bad in fixes.get("bad_prints", []):
        stamp = pd.Timestamp(bad["date"]).date()
        mask = pd.Series([d.date() != stamp for d in close.index], index=close.index)
        if (~mask).any():
            close = close[mask]
            applied.append({"type": "bad_print", "date": bad["date"],
                            "sessions_dropped": int((~mask).sum())})

    for split in sorted(fixes.get("splits", []), key=lambda s: s["date"]):
        stamp = pd.Timestamp(split["date"]).tz_localize(close.index.tz)
        before = close.index < stamp
        if before.any():
            close = close.copy()
            close[before] = close[before] / split["ratio"]
            applied.append({"type": "split", "date": split["date"],
                            "ratio": split["ratio"],
                            "sessions_rescaled": int(before.sum())})
    return close, applied


def compute(close):
    """All price-derived indicators for one instrument."""
    close = pd.Series(close).dropna()
    n = len(close)
    breaks = detect_breaks(close)
    out = {
        "trading_days": n,
        "last_price": float(close.iloc[-1]) if n else np.nan,
        "insufficient_history": n < config.MIN_TRADING_DAYS,
        "price_breaks": breaks,
        "data_suspect": bool(breaks),
    }
    if n < config.MIN_TRADING_DAYS:
        # Reported as missing, never as a finding. A short series is a gap in
        # coverage, not a negative fact about the instrument.
        return out
    if breaks:
        # Indicators computed across a broken series are confident nonsense.
        # Last price is still reported — that part is observably right — but
        # nothing derived from history is.
        return out

    out["rsi_14"] = wilder_rsi(close)
    out["return_1m_pct"] = _pct_change_over(close, 21)
    out["return_3m_pct"] = _pct_change_over(close, 63)
    out["return_12m_pct"] = _pct_change_over(close, 252)

    ma_days = config.MOVING_AVERAGE_DAYS
    if n >= ma_days:
        ma = float(close.tail(ma_days).mean())
        out["ma_200"] = ma
        out["vs_ma_200_pct"] = float((close.iloc[-1] / ma - 1) * 100)
        out["above_ma_200"] = bool(close.iloc[-1] > ma)

    window = config.VOLATILITY_WINDOW_DAYS
    daily = close.pct_change().dropna().tail(window)
    out["volatility_1y_pct"] = float(daily.std() * np.sqrt(252) * 100)
    out["max_drawdown_2y_pct"] = _max_drawdown(close.tail(504))

    buy, sell = limit_band(out["last_price"], out["volatility_1y_pct"])
    out["buy_limit_1m"] = buy
    out["sell_limit_1m"] = sell
    return out


def trend_score(ind):
    """
    Trend, 0-2. Deliberately small: it breaks ties between names of similar
    health and valuation. It is not allowed to drive a verdict on its own.
    """
    if ind.get("insufficient_history") or ind.get("data_suspect"):
        return None
    score = 0
    if ind.get("above_ma_200"):
        score += config.TREND_ABOVE_MA_POINTS
    r12 = ind.get("return_12m_pct")
    if r12 is not None and not pd.isna(r12) and r12 > 0:
        score += config.TREND_POSITIVE_12M_POINTS
    return score


def fetch_history(items):
    """
    Download close-price history for every instrument.

    An empty frame raises rather than returning zeros: a throttled feed must
    stop the run, never look like a set of flat prices.
    """
    symbols = [common.yahoo_symbol(i["code"]) for i in items]
    period = f"{config.HISTORY_YEARS}y"

    # Same-day cache only. Never extended incrementally — adjusted prices
    # change retroactively with every dividend, so an appended series would
    # silently diverge from a clean fetch. See config.PRICE_CACHE_TTL_HOURS.
    cached = common.cache_get("price_history",
                              ttl_hours=config.PRICE_CACHE_TTL_HOURS)
    if cached and set(symbols) <= set(cached["series"]):
        idx = pd.DatetimeIndex([pd.Timestamp(d) for d in cached["dates"]])
        return pd.DataFrame(
            {sym: cached["series"][sym] for sym in symbols}, index=idx)

    def fetch():
        return yf.download(
            symbols, period=period, interval="1d",
            auto_adjust=True, progress=False, threads=False, group_by="column",
        )

    frame = common.with_retry(fetch)
    if frame is None or frame.empty:
        raise common.DataFeedError(
            f"price feed returned nothing for {len(symbols)} symbols — "
            f"treat as a failed run, not as missing data"
        )

    close = frame["Close"] if "Close" in frame.columns.get_level_values(0) else frame
    if isinstance(close, pd.Series):
        close = close.to_frame(symbols[0])

    common.cache_put("price_history", {
        "dates": [ts.isoformat() for ts in close.index],
        "series": {sym: [None if pd.isna(v) else float(v)
                         for v in close[sym]] for sym in close.columns},
    })
    return close


def build(items=None, keep_series=False):
    """
    Resolve the universe, fetch history, compute indicators for each.

    `keep_series` attaches the corrected close series as `_close` for callers
    that need it (valuation builds daily ratio series on top). It is dropped
    before serialisation — the underscore marks it as not for the run file.
    """
    items = items if items is not None else universe_mod.resolve()
    close = fetch_history(items)
    fixes = universe_mod.corrections()

    rows = []
    for item in items:
        symbol = common.yahoo_symbol(item["code"])
        series = close[symbol].dropna() if symbol in close.columns else pd.Series(dtype=float)
        series, applied = apply_corrections(series, fixes.get(item["code"]))
        row = dict(item)
        row["corrections_applied"] = applied
        row.update(compute(series))
        row["trend_score"] = trend_score(row)
        row["as_of"] = series.index[-1].strftime("%Y-%m-%d") if len(series) else None
        if keep_series:
            row["_close"] = series
        rows.append(row)

    missing = [r["code"] for r in rows if r.get("trading_days", 0) == 0]
    if len(missing) > len(rows) // 2:
        raise common.DataFeedError(
            f"{len(missing)} of {len(rows)} instruments returned no price data. "
            f"That is a feed failure, not a universe problem: {missing}"
        )
    return rows


def main(argv=None):
    rows = build()
    hdr = (f"{'CODE':<6} {'NAME':<34} {'PRICE':>10} {'RSI':>6} "
           f"{'1M%':>7} {'3M%':>7} {'12M%':>8} {'vsMA%':>7} {'VOL%':>6} {'TR':>3}")
    print(hdr); print("-" * len(hdr))

    def fmt(v, nd=1):
        return "—" if v is None or (isinstance(v, float) and pd.isna(v)) else f"{v:.{nd}f}"

    for r in rows:
        if r.get("data_suspect"):
            first = r["price_breaks"][0]
            print(f"{r['code']:<6} {universe_mod.display_name(r)[:34]:<34} "
                  f"{fmt(r.get('last_price'), 1):>10}   ⚠ DATA SUSPECT — "
                  f"{first['looks_like']} on {first['date']}"
                  + (f" (+{len(r['price_breaks']) - 1} more)"
                     if len(r["price_breaks"]) > 1 else ""))
            continue
        if r.get("insufficient_history"):
            print(f"{r['code']:<6} {universe_mod.display_name(r)[:34]:<34} "
                  f"{'insufficient history':>52}")
            continue
        print(f"{r['code']:<6} {universe_mod.display_name(r)[:34]:<34} "
              f"{fmt(r.get('last_price'), 1):>10} {fmt(r.get('rsi_14')):>6} "
              f"{fmt(r.get('return_1m_pct')):>7} {fmt(r.get('return_3m_pct')):>7} "
              f"{fmt(r.get('return_12m_pct')):>8} {fmt(r.get('vs_ma_200_pct')):>7} "
              f"{fmt(r.get('volatility_1y_pct')):>6} {str(r.get('trend_score','—')):>3}")

    dates = {r["as_of"] for r in rows if r.get("as_of")}
    suspect = [r["code"] for r in rows if r.get("data_suspect")]
    print(f"\n{len(rows)} instruments · prices as of "
          f"{sorted(dates)[-1] if dates else 'n/a'} · {len(suspect)} suspect")
    if suspect:
        print(f"not scored, series unusable: {', '.join(suspect)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
