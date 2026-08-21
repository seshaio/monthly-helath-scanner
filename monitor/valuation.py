"""
Valuation against each name's own history, not against the market.

The point of a percentile here is that "expensive" means dear *relative to
what this business has traded at*, which is a question the data can answer.
Whether it is dear relative to what it is worth is not, and this module does
not pretend otherwise.

Two deliberate omissions:

  * Sell-side consensus does not score. It is fetched and shown elsewhere as
    one input among several, because it is structurally bullish and revises
    after prices move as often as before.
  * ETFs get nothing from here. P/E and book value of a gold trust or an index
    tracker are not weak signals, they are category errors. ETFs need their
    own rubric — tracking difference, spread, premium to NAV, and the
    valuation of the underlying index.

Ratios are built as daily series: the price moves every day, the fundamentals
step when results are published. Fundamentals are lagged by a publication
delay so a run never uses figures before they were public — without that the
whole history is contaminated by hindsight and every percentile is wrong in
the flattering direction.
"""

import sys

import numpy as np
import pandas as pd
import yfinance as yf

import common
import config
from monitor import universe as universe_mod


def _row(frame, *names):
    """First matching line item, as a Series indexed by period end."""
    if frame is None or frame.empty:
        return None
    for name in names:
        if name in frame.index:
            series = frame.loc[name].dropna()
            if not series.empty:
                return series.astype(float)
    return None


def fetch_fundamentals(code):
    """Annual statements, share count and dividend history for one equity."""
    cache_key = f"fundamentals_{code}"
    cached = common.cache_get(cache_key)
    if cached is not None:
        return _revive(cached)

    ticker = yf.Ticker(common.yahoo_symbol(code))

    def grab():
        return {
            "income": ticker.income_stmt,
            "balance": ticker.balance_sheet,
            "cash": ticker.cashflow,
            "dividends": ticker.dividends,
            "info": ticker.info or {},
        }

    raw = common.with_retry(grab)
    payload = {
        "eps": _series_to_dict(_row(raw["income"], "Diluted EPS", "Basic EPS")),
        "net_income": _series_to_dict(_row(raw["income"], "Net Income Common Stockholders", "Net Income")),
        "shares": _series_to_dict(_row(raw["income"], "Diluted Average Shares")),
        "ebit": _series_to_dict(_row(raw["income"], "EBIT", "Operating Income")),
        "equity": _series_to_dict(_row(raw["balance"], "Stockholders Equity", "Total Equity Gross Minority Interest")),
        "debt": _series_to_dict(_row(raw["balance"], "Total Debt")),
        "cash_eq": _series_to_dict(_row(raw["balance"], "Cash And Cash Equivalents", "Cash Cash Equivalents And Short Term Investments")),
        "fcf": _series_to_dict(_row(raw["cash"], "Free Cash Flow")),
        "dividends": {str(k.date()): float(v) for k, v in raw["dividends"].items()}
                     if raw["dividends"] is not None and len(raw["dividends"]) else {},
        "sector": raw["info"].get("sector"),
        "industry": raw["info"].get("industry"),
    }
    common.cache_put(cache_key, payload)
    return _revive(payload)


def _series_to_dict(series):
    if series is None:
        return {}
    return {str(pd.Timestamp(k).date()): float(v) for k, v in series.items()}


def _revive(payload):
    out = dict(payload)
    for key in ("eps", "net_income", "shares", "ebit", "equity", "debt",
                "cash_eq", "fcf", "dividends"):
        raw = payload.get(key) or {}
        out[key] = pd.Series(
            {pd.Timestamp(k): v for k, v in raw.items()}, dtype=float
        ).sort_index()
    return out


def _stepped(annual, index, lag_days):
    """
    Expand annual figures onto the daily price index.

    Each period's value applies only from `lag_days` after the period end —
    the delay between a fiscal year closing and its results being published.
    Applying it from the period end itself would let the run "know" earnings
    weeks before the market did, which flatters every historical percentile.
    """
    if annual is None or annual.empty:
        return pd.Series(np.nan, index=index)

    tz = index.tz
    stamps, values = [], []
    for period_end, value in annual.items():
        effective = pd.Timestamp(period_end) + pd.Timedelta(days=lag_days)
        if tz is not None:
            effective = effective.tz_localize(tz)
        stamps.append(effective)
        values.append(value)

    stepped = pd.Series(values, index=pd.DatetimeIndex(stamps)).sort_index()
    return stepped.reindex(stepped.index.union(index)).ffill().reindex(index)


def _positive(series):
    """Non-positive denominators make a ratio meaningless, not cheap."""
    return series.where(series > 0)


def build_ratios(close, fundamentals):
    """Daily series for every anchor. Missing anchors are simply absent."""
    lag = config.FUNDAMENTALS_PUBLICATION_LAG_DAYS
    idx = close.index

    eps = fundamentals["eps"]
    if eps.empty and not fundamentals["net_income"].empty and not fundamentals["shares"].empty:
        eps = (fundamentals["net_income"] / fundamentals["shares"]).dropna()

    shares = _stepped(fundamentals["shares"], idx, lag)
    ratios = {}

    eps_d = _positive(_stepped(eps, idx, lag))
    if eps_d.notna().any():
        ratios["pe"] = close / eps_d

    equity = _stepped(fundamentals["equity"], idx, lag)
    bvps = _positive(equity / shares)
    if bvps.notna().any():
        ratios["pb"] = close / bvps

    ebit = _positive(_stepped(fundamentals["ebit"], idx, lag))
    debt = _stepped(fundamentals["debt"], idx, lag).fillna(0)
    cash_eq = _stepped(fundamentals["cash_eq"], idx, lag).fillna(0)
    if ebit.notna().any() and shares.notna().any():
        enterprise_value = close * shares + debt - cash_eq
        ratios["ev_ebit"] = (enterprise_value / ebit).where(enterprise_value > 0)

    fcf_ps = _stepped(fundamentals["fcf"], idx, lag) / shares
    if fcf_ps.notna().any():
        ratios["fcf_yield"] = fcf_ps / close * 100

    dividends = fundamentals["dividends"]
    if not dividends.empty:
        if dividends.index.tz is None and idx.tz is not None:
            dividends.index = dividends.index.tz_localize(idx.tz)
        elif dividends.index.tz is not None and idx.tz is not None:
            dividends.index = dividends.index.tz_convert(idx.tz)
        ttm = dividends.reindex(dividends.index.union(idx)).fillna(0).rolling("365D").sum()
        ratios["dividend_yield"] = (ttm.reindex(idx) / close * 100).replace(0, np.nan)

    return ratios


def percentile_of_latest(series):
    """
    Where does today's value sit within its own history, 0-100?

    Low means cheap for a multiple and dear for a yield; callers invert the
    yield anchors. Returns None rather than a number when there is too little
    history to rank against — a percentile from six observations is noise
    wearing a decimal point.
    """
    series = pd.Series(series).replace([np.inf, -np.inf], np.nan).dropna()
    if len(series) < config.VALUATION_MIN_OBSERVATIONS:
        return None, None
    latest = float(series.iloc[-1])
    return float((series < latest).mean() * 100), latest


def is_financial(fundamentals, code):
    """Banks and insurers: EV/EBIT and free cash flow are meaningless."""
    if code in config.FINANCIAL_CODES:
        return True
    sector = (fundamentals.get("sector") or "").lower()
    return "financial" in sector or "insurance" in sector or "bank" in sector


def assess(code, close, fundamentals):
    """Percentile every available anchor and turn the mean into a 0-4 score."""
    result = {
        "anchors": {}, "valuation_score": None, "valuation_label": None,
        "mean_percentile": None, "is_financial": False, "skipped_anchors": {},
    }
    financial = is_financial(fundamentals, code)
    result["is_financial"] = financial

    ratios = build_ratios(close, fundamentals)
    for name in config.VALUATION_ANCHORS:
        if financial and name in config.FINANCIAL_EXCLUDED_ANCHORS:
            result["skipped_anchors"][name] = "not meaningful for a financial"
            continue
        if name not in ratios:
            result["skipped_anchors"][name] = "not reported by the feed"
            continue

        pct, latest = percentile_of_latest(ratios[name])
        if pct is None:
            result["skipped_anchors"][name] = "insufficient history to rank"
            continue

        # A high yield is cheap, so its percentile runs the other way. Getting
        # this backwards is the easiest silent error in the whole module.
        inverted = name in config.VALUATION_ANCHORS_INVERTED
        result["anchors"][name] = {
            "value": latest,
            "percentile": 100 - pct if inverted else pct,
            "raw_percentile": pct,
            "inverted": inverted,
        }

    available = result["anchors"]
    if len(available) < config.VALUATION_MIN_ANCHORS:
        result["valuation_label"] = "INSUFFICIENT DATA"
        return result

    percentiles = [a["percentile"] for a in available.values()]
    mean_pct = float(np.mean(percentiles))
    result["mean_percentile"] = mean_pct

    # Anchors that disagree violently are not averaged into a verdict quietly.
    # A wide spread means the anchors are measuring genuinely different things
    # about the business, and the mean describes none of them.
    spread = float(max(percentiles) - min(percentiles))
    result["percentile_spread"] = spread
    result["anchors_disagree"] = spread >= config.VALUATION_DISPERSION_THRESHOLD
    if result["anchors_disagree"]:
        cheapest = min(available.items(), key=lambda kv: kv[1]["percentile"])
        dearest = max(available.items(), key=lambda kv: kv[1]["percentile"])
        result["disagreement"] = {
            "cheapest_anchor": cheapest[0],
            "cheapest_percentile": cheapest[1]["percentile"],
            "dearest_anchor": dearest[0],
            "dearest_percentile": dearest[1]["percentile"],
        }
    for ceiling, score in config.VALUATION_BANDS:
        if mean_pct <= ceiling:
            result["valuation_score"] = score
            break
    result["valuation_label"] = config.VALUATION_LABELS[result["valuation_score"]]
    if result["anchors_disagree"]:
        result["valuation_label"] += " — anchors disagree"

    expensive = sum(1 for a in available.values()
                    if a["percentile"] >= config.TRIM_PERCENTILE)
    result["anchors_expensive"] = expensive
    result["trim_candidate"] = expensive >= config.TRIM_MIN_ANCHORS_EXPENSIVE
    return result


def build(rows):
    """Attach a valuation assessment to each equity row. ETFs are skipped."""
    throttle = common.Throttle(config.REQUEST_DELAY_SECONDS)
    for row in rows:
        if row["asset_type"] != "Equity":
            row["valuation"] = {
                "valuation_label": "ETF — separate rubric",
                "valuation_score": None,
            }
            continue
        if row.get("data_suspect") or row.get("insufficient_history"):
            row["valuation"] = {
                "valuation_label": "not assessed — price series unusable",
                "valuation_score": None,
            }
            continue
        throttle.wait()
        fundamentals = fetch_fundamentals(row["code"])
        row["valuation"] = assess(row["code"], row["_close"], fundamentals)
    return rows


def main(argv=None):
    from monitor import indicators
    rows = indicators.build(keep_series=True)
    rows = build(rows)

    print(f"{'CODE':<6} {'NAME':<32} {'PE':>7} {'PB':>7} {'EV/EBIT':>8} "
          f"{'FCF%':>7} {'DIV%':>7} {'MEAN':>6} {'SC':>3}  LABEL")
    print("-" * 108)
    for row in rows:
        val = row.get("valuation", {})
        anchors = val.get("anchors", {})

        def cell(name):
            a = anchors.get(name)
            return "—" if not a else f"{a['percentile']:.0f}"

        score = val.get("valuation_score")
        print(f"{row['code']:<6} {universe_mod.display_name(row)[:32]:<32} "
              f"{cell('pe'):>7} {cell('pb'):>7} {cell('ev_ebit'):>8} "
              f"{cell('fcf_yield'):>7} {cell('dividend_yield'):>7} "
              f"{(f'{val['mean_percentile']:.0f}' if val.get('mean_percentile') is not None else '—'):>6} "
              f"{(str(score) if score is not None else '—'):>3}  {val.get('valuation_label')}")
        if val.get("anchors_disagree"):
            d = val["disagreement"]
            print(f"{'':>6} {'':<32} ⚠ {d['cheapest_anchor']} at "
                  f"{d['cheapest_percentile']:.0f} vs {d['dearest_anchor']} at "
                  f"{d['dearest_percentile']:.0f} — the mean describes neither")
    print("\nColumns are percentiles against each name's own 5-year history.")
    print("Low = cheap. Yield anchors are already inverted, so low means cheap there too.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
