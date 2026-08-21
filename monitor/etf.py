"""
The ETF rubric.

An ETF has no earnings, no book value and no business to be healthy, so none
of the equity ladder applies. What can actually go wrong with a fund is
structural — it gets too small, too thinly traded, or drifts from what it
claims to track — and that carries the weight health carries for an equity.
Both tables then end on the same 0-10 score and the same verdict words.

Two honest limits, both stated in the output rather than hidden:

  * The feed does not timestamp NAV, so premium and discount are indicative.
  * There is no history for an index multiple, so the underlying valuation is
    scored against a declared long-run reference in config.py. That reference
    is a judgement. It is editable, and the score moves when it is edited.
"""

import sys

import yfinance as yf

import common
import config
from monitor import universe as universe_mod


def fetch_profile(code):
    """Fund facts from the feed, cached."""
    cached = common.cache_get(f"etf_{code}")
    if cached is not None:
        return cached

    def grab():
        return yf.Ticker(common.yahoo_symbol(code)).info or {}

    info = common.with_retry(grab)
    profile = {
        "aum_jpy": info.get("totalAssets"),
        "nav": info.get("navPrice"),
        "bid": info.get("bid"),
        "ask": info.get("ask"),
        "yield_pct": (info.get("yield") or 0) * 100 or None,
        "index_pe": info.get("trailingPE"),
        "beta_3y": info.get("beta3Year"),
        "provider": info.get("fundFamily"),
    }
    common.cache_put(f"etf_{code}", profile)
    return profile


def spread_pct(profile):
    bid, ask = profile.get("bid"), profile.get("ask")
    if not bid or not ask or ask < bid:
        return None
    mid = (bid + ask) / 2
    return (ask - bid) / mid * 100 if mid else None


def premium_pct(profile, price):
    """Price against NAV. Indicative — the feed does not timestamp NAV."""
    nav = profile.get("nav")
    if not nav or not price:
        return None
    return (price / nav - 1) * 100


def structural_score(profile, price):
    """
    0-4, and deliberately parallel to the equity health ladder: 4 is sound,
    2 is worth noting, 0 is at risk of failing its holder.

    It starts at sound and deducts, rather than accumulating points for
    excellence. The first cut of this scored 1658 — a usable fund with ¥29bn
    and a 0.32% spread — at 1 of 4, which dragged it to SELL. A merely
    unremarkable wrapper is not a reason to exit an asset; only a wrapper at
    risk of closing or costing real money to leave is.

    Premium to NAV is deliberately absent. The feed does not timestamp NAV, so
    scoring it docked every fund here for a stale number.
    """
    score, notes = 4, []

    aum = profile.get("aum_jpy")
    if aum is None:
        score -= 1
        notes.append("AUM not reported")
    elif aum < config.ETF_MIN_AUM_JPY:
        # Small enough that closure and delisting are live risks.
        score -= 3
        notes.append(f"AUM ¥{aum / 1e9:.1f}bn — closure risk")
    elif aum < config.ETF_GOOD_AUM_JPY:
        score -= 1
        notes.append(f"AUM ¥{aum / 1e9:.0f}bn — modest")

    spread = spread_pct(profile)
    if spread is None:
        score -= 1
        notes.append("no quote")
    elif spread > config.ETF_MAX_SPREAD_PCT * 2:
        score -= 2
        notes.append(f"spread {spread:.2f}% — exit costs bite")
    elif spread > config.ETF_MAX_SPREAD_PCT:
        score -= 1
        notes.append(f"spread {spread:.2f}% — wide")

    premium = premium_pct(profile, price)
    if premium is not None and abs(premium) >= config.ETF_NOTABLE_PREMIUM_PCT:
        notes.append(f"{premium:+.1f}% vs NAV — larger than a stale NAV "
                     f"explains, worth a look")

    return max(0, score), notes


def underlying_valuation(code, profile, assumption=None):
    """
    Current index multiple against its long-run reference.

    A declared assumption from universe.toml can override the reference —
    applied mechanically and labelled in the output, so the report always
    shows WHICH multiple the score was measured against and why.
    """
    out = {"index_pe": None, "reference_pe": None, "ratio": None,
           "score": None, "label": None, "suspect": False, "assumption": None}

    if code in config.ETF_NO_EARNINGS:
        out["label"] = "no earnings — commodity"
        return out

    pe = profile.get("index_pe")
    reference = config.ETF_REFERENCE_PE.get(code)
    override = (assumption or {}).get("reference_pe")
    if override and reference is not None:
        out["assumption"] = override
        reference = override["value"]
    if pe is None or reference is None:
        out["label"] = "no index multiple available"
        return out

    low, high = config.ETF_PLAUSIBLE_PE_RANGE
    if not (low <= pe <= high):
        # An index multiple outside this range is a broken figure, not a
        # cheap market. 2559 reported 3.02 on the first live run.
        out["index_pe"] = pe
        out["suspect"] = True
        out["label"] = f"index P/E {pe:.1f} implausible — not scored"
        return out

    ratio = pe / reference
    out.update({"index_pe": pe, "reference_pe": reference, "ratio": ratio})
    for ceiling, score in config.ETF_VALUATION_BANDS:
        if ratio <= ceiling:
            out["score"] = score
            break
    out["label"] = (f"index at {pe:.1f}x vs {reference:.0f}x reference "
                    f"({ratio - 1:+.0%})")
    if out["assumption"]:
        out["label"] += (f" — scenario reference, declared "
                         f"{out['assumption']['date']}: "
                         f"{out['assumption']['note'][:60]}…")
    return out


def assess(row, assumption=None):
    """Full ETF assessment for one row."""
    profile = fetch_profile(row["code"])
    price = row.get("last_price")

    structural, notes = structural_score(profile, price)
    valuation = underlying_valuation(row["code"], profile, assumption)

    return {
        "profile": profile,
        "spread_pct": spread_pct(profile),
        "premium_pct": premium_pct(profile, price),
        "structural_score": structural,
        "structural_notes": notes,
        "underlying": valuation,
        "valuation_score": valuation["score"],
        "fx": row.get("fx"),
    }


def build(rows):
    """Attach an ETF assessment to every ETF row."""
    declared = universe_mod.assumptions()
    throttle = common.Throttle(config.REQUEST_DELAY_SECONDS)
    for row in rows:
        if row["asset_type"] != "ETF":
            continue
        if row.get("data_suspect") or row.get("insufficient_history"):
            row["etf"] = {"structural_score": None, "valuation_score": None,
                          "structural_notes": ["price series unusable"]}
            continue
        throttle.wait()
        row["etf"] = assess(row, declared.get(row["code"]))
    return rows


def main(argv=None):
    from monitor import indicators
    rows = build(indicators.build())
    etfs = [r for r in rows if r["asset_type"] == "ETF"]

    def cell(value, fmt, width):
        return f"{(format(value, fmt) if value is not None else '—'):>{width}}"

    print(f"{'CODE':<6} {'NAME':<38} {'AUM¥bn':>8} {'SPRD%':>6} "
          f"{'vNAV%':>6} {'STRUCT':>6} {'VAL':>4}  UNDERLYING")
    print("-" * 112)
    for row in etfs:
        assessment = row["etf"]
        profile = assessment.get("profile", {})
        aum = profile.get("aum_jpy")
        structural = assessment.get("structural_score")
        valuation = assessment.get("valuation_score")
        print(f"{row['code']:<6} {universe_mod.display_name(row)[:38]:<38} "
              f"{cell(aum / 1e9 if aum else None, ',.0f', 8)} "
              f"{cell(assessment.get('spread_pct'), '.2f', 6)} "
              f"{cell(assessment.get('premium_pct'), '+.1f', 6)} "
              f"{(f'{structural}/4' if structural is not None else '—'):>6} "
              f"{(f'{valuation}/4' if valuation is not None else '—'):>4}  "
              f"{assessment.get('underlying', {}).get('label', '')}")
        for note in assessment.get("structural_notes", []):
            print(f"{'':>6} {'':<38} ⚠ {note}")
    print("\nNAV is indicative — the feed does not timestamp it.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
