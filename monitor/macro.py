"""
The macro dashboard and the five standing lenses.

"Where are markets heading" written freehand produces fluent text driven by
whatever was in the news that week. So the dashboard is a fixed set of levels
and 3-month changes, and the five lenses are scored by rules in config.py —
the same lenses, the same scale, every run. Movement is the signal; a lens
score means nothing in isolation and everything against last month's.

The thresholds are judgments and say so. What is NOT a judgment is that the
same inputs always produce the same score: the narrative is generated from
the arithmetic, never the other way around.

Honest limits: no JGB yields, no CPI, no wage data in this feed. The Japan
lens runs on equity trend alone and is labelled accordingly. The yield curve
is 10y minus 13-week T-bill — a usable proxy for 2s10s, not the thing itself.
"""

import sys

import pandas as pd
import yfinance as yf

import common
import config


def fetch_dashboard():
    """Six months of daily closes for every macro ticker, cached same-day."""
    cached = common.cache_get("macro_history",
                              ttl_hours=config.PRICE_CACHE_TTL_HOURS)
    if cached:
        # utc=True: US series straddle a DST change, so their offsets are
        # mixed within one list. Only positions matter to the lens math.
        return {name: pd.Series(vals["values"],
                                index=pd.to_datetime(vals["dates"], utc=True))
                for name, vals in cached.items()}

    out = {}
    throttle = common.Throttle(config.REQUEST_DELAY_SECONDS)
    for name, symbol in config.MACRO_TICKERS.items():
        throttle.wait()
        try:
            hist = common.with_retry(
                lambda s=symbol: yf.Ticker(s).history(period="6mo")["Close"].dropna())
        except Exception:                            # noqa: BLE001 - recorded
            hist = pd.Series(dtype=float)
        out[name] = hist

    missing = [n for n, h in out.items() if h.empty]
    if len(missing) > len(out) // 2:
        raise common.DataFeedError(
            f"macro feed returned nothing for {missing} — failed run, "
            f"not a quiet market")

    common.cache_put("macro_history", {
        name: {"dates": [ts.isoformat() for ts in h.index],
               "values": [float(v) for v in h]}
        for name, h in out.items()})
    return out


def _level_and_change(series):
    """Latest level and % change over the lookback window."""
    series = series.dropna()
    if series.empty:
        return None, None
    level = float(series.iloc[-1])
    back = config.MACRO_LOOKBACK_SESSIONS
    if len(series) <= back:
        return level, None
    prior = float(series.iloc[-back - 1])
    return level, (level / prior - 1) * 100 if prior else None


def build_dashboard(histories):
    return {name: dict(zip(("level", "chg_3m_pct"), _level_and_change(h)))
            for name, h in histories.items()}


# ---------------------------------------------------------------------------
# The five lenses. Each returns (score, basis) — the basis string is the
# narrative, generated FROM the rule that fired, so prose and number can
# never disagree.
# ---------------------------------------------------------------------------

def lens_ai_bubble(dash, t):
    sox = (dash.get("sox") or {}).get("chg_3m_pct")
    spx = (dash.get("sp500") or {}).get("chg_3m_pct")
    if sox is None:
        return None, "SOX unavailable"
    if sox <= t["sox_rollover_pct"] and (spx or 0) > 0:
        return -2, (f"SOX {sox:+.1f}% over 3m while the S&P is up — the AI "
                    f"complex is rolling over without the market noticing yet")
    if sox <= t["sox_rollover_pct"]:
        return -1, f"SOX {sox:+.1f}% over 3m — the complex is deflating"
    if sox >= t["sox_froth_pct"]:
        return -1, f"SOX {sox:+.1f}% in 3m — froth, not fundamentals, at that pace"
    if sox > 0 and (spx or 0) > 0:
        return 1, f"SOX {sox:+.1f}% in line with the broad market"
    return 0, f"SOX {sox:+.1f}% over 3m — neither breaking nor frothing"


def lens_usdjpy(dash, t):
    chg = (dash.get("usdjpy") or {}).get("chg_3m_pct")
    level = (dash.get("usdjpy") or {}).get("level")
    if chg is None:
        return None, "USD/JPY unavailable"
    where = f"USD/JPY {level:.0f}, {chg:+.1f}% over 3m"
    if abs(chg) <= t["yen_calm_band_pct"]:
        return 1, f"{where} — stable, which is what this portfolio wants"
    if chg > t["yen_sharp_pct"]:
        return 0, f"{where} — a weaker yen helps, but at this pace it invites intervention"
    if chg > 0:
        return 1, f"{where} — orderly yen weakness, a tailwind for USD assets"
    if chg < -t["yen_sharp_pct"]:
        return -2, f"{where} — sharp yen strength, a direct hit to every unhedged USD position"
    return -1, f"{where} — yen firming against the unhedged USD exposure"


def lens_us_recession(dash, t):
    tnx = (dash.get("us10y") or {}).get("level")
    irx = (dash.get("us13w") or {}).get("level")
    vix = (dash.get("vix") or {}).get("level")
    if tnx is None or irx is None:
        return None, "US rates unavailable"
    curve = tnx - irx
    where = f"10y−13w {curve:+.2f}pp, VIX {vix:.0f}" if vix else f"10y−13w {curve:+.2f}pp"
    if vix and vix >= t["vix_stress"]:
        return -2, f"{where} — volatility at stress levels"
    if curve <= t["curve_deep_inversion"]:
        return -2, f"{where} — deeply inverted, the classic pre-recession shape"
    if curve < 0:
        return -1, f"{where} — inverted"
    if vix and vix < t["vix_calm"]:
        return 1, f"{where} — positive curve, calm volatility"
    return 0, where


def lens_japan_domestic(dash, t):
    chg = (dash.get("topix") or {}).get("chg_3m_pct")
    if chg is None:
        return None, "TOPIX proxy unavailable"
    where = f"TOPIX (via 1306) {chg:+.1f}% over 3m"
    note = " [equity trend only — no JGB/CPI in this feed]"
    if chg >= t["equity_trend_pct"]:
        return 1, where + " — a real uptrend" + note
    if chg <= -t["equity_trend_pct"]:
        return -1, where + " — a real downtrend" + note
    return 0, where + note


def lens_geopolitics(dash, t):
    oil = (dash.get("wti") or {}).get("chg_3m_pct")
    gold = (dash.get("gold") or {}).get("chg_3m_pct")
    if oil is None or gold is None:
        return None, "oil or gold unavailable"
    where = f"WTI {oil:+.1f}%, gold {gold:+.1f}% over 3m"
    if oil >= t["oil_spike_pct"] and gold >= t["gold_spike_pct"]:
        return -2, f"{where} — both spiking together is the supply-shock signature"
    if oil >= t["oil_spike_pct"]:
        return -1, f"{where} — energy under pressure"
    if gold >= t["gold_spike_pct"]:
        return 0, f"{where} — gold bid but oil calm reads monetary, not war"
    return 0, f"{where} — calm"


LENSES = {
    "ai_bubble": ("AI bubble", lens_ai_bubble),
    "usdjpy": ("USD/JPY", lens_usdjpy),
    "us_recession": ("US recession", lens_us_recession),
    "japan_domestic": ("Japan domestic", lens_japan_domestic),
    "geopolitics": ("War / geopolitics", lens_geopolitics),
}


def score_lenses(dashboard):
    thresholds = config.MACRO_THRESHOLDS
    return {key: {"name": name, "score": result[0], "basis": result[1]}
            for key, (name, fn) in LENSES.items()
            for result in [fn(dashboard, thresholds)]}


def market_score(lenses):
    """5 + half the lens sum, clamped to 0-10. None if any lens failed."""
    scores = [l["score"] for l in lenses.values()]
    if any(v is None for v in scores):
        return None, "not computed — a lens has no data"
    raw = 5 + sum(scores) / 2
    value = int(max(0, min(10, round(raw))))
    for ceiling, label in config.MARKET_SCORE_LABELS:
        if value <= ceiling:
            return value, label
    return value, "NEUTRAL"


def build():
    histories = fetch_dashboard()
    dashboard = build_dashboard(histories)
    lenses = score_lenses(dashboard)
    value, label = market_score(lenses)
    return {"dashboard": dashboard, "lenses": lenses,
            "market_score": value, "market_label": label}


def main(argv=None):
    out = build()
    print(f"MARKET SCORE: {out['market_score']}/10 — {out['market_label']}\n")
    for key, lens in out["lenses"].items():
        score = lens["score"]
        print(f"  {lens['name']:<18} {score if score is not None else '—':>3}   {lens['basis']}")
    print()
    for name, row in out["dashboard"].items():
        lvl, chg = row["level"], row["chg_3m_pct"]
        print(f"  {name:<10} {lvl:>12,.2f}  {f'{chg:+.1f}%' if chg is not None else '—':>8}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
