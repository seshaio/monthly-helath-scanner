"""
Render the monthly page.

One page: one score, one table, one verdict per name. If it does not help
answer buy / keep / sell, it does not print.

While components are still being built this renderer states plainly what is
missing and refuses to score without them. A partial score presented as a
whole one is the same class of error as a feed failure presented as a
finding — it reads as complete and is not.
"""

import os
import sys
from datetime import datetime

import pandas as pd

import common
import config
from monitor import indicators
from monitor import universe as universe_mod
from monitor import valuation as valuation_mod
from monitor import etf as etf_mod
from monitor import verdict as verdict_mod


# Components not yet built. Each one contributes to the score, so while any
# is outstanding the score is partial and the verdict is withheld.
PENDING = {
    "health": ("business health ladder and triggers", 4),
    "macro": ("macro dashboard and the five lenses", None),
    "portfolio": ("correlation clusters and FX exposure", None),
    "earnings": ("earnings calendar and the defer gate", None),
}

EQUITY_IMPLEMENTED = (config.TREND_ABOVE_MA_POINTS
                      + config.TREND_POSITIVE_12M_POINTS
                      + max(score for _ceiling, score in config.VALUATION_BANDS))
IMPLEMENTED_POINTS = EQUITY_IMPLEMENTED
TOTAL_POINTS = 10


def _reason(row):
    """A short, honest reason from what has actually been computed."""
    if row.get("data_suspect"):
        return f"**data suspect** — {row['price_breaks'][0]['looks_like']}"
    if row.get("insufficient_history"):
        return "insufficient price history"

    bits = []
    val = row.get("valuation") or {}
    if val.get("anchors_disagree"):
        d = val["disagreement"]
        bits.append(f"**anchors disagree** — {d['cheapest_anchor']} "
                    f"{d['cheapest_percentile']:.0f} vs {d['dearest_anchor']} "
                    f"{d['dearest_percentile']:.0f}")
    elif val.get("mean_percentile") is not None:
        bits.append(f"{val['valuation_label'].lower()} "
                    f"({_ordinal(val['mean_percentile'])} pct)")
    elif val.get("valuation_label"):
        bits.append(val["valuation_label"])

    rsi = row.get("rsi_14")
    if rsi is not None and not pd.isna(rsi):
        if rsi >= 70:
            bits.append(f"RSI {rsi:.0f} — overbought")
        elif rsi <= 30:
            bits.append(f"RSI {rsi:.0f} — oversold")

    vs_ma = row.get("vs_ma_200_pct")
    if vs_ma is not None and not pd.isna(vs_ma):
        bits.append(f"{'above' if vs_ma > 0 else 'below'} 200d by {abs(vs_ma):.0f}%")

    r12 = row.get("return_12m_pct")
    if r12 is not None and not pd.isna(r12) and abs(r12) > 40:
        bits.append(f"{'+' if r12 > 0 else ''}{r12:.0f}% over 12m")

    return ", ".join(bits) if bits else "nothing notable in price"


def _ordinal(value):
    """23rd, not 23th."""
    n = int(round(value))
    if 10 <= n % 100 <= 20:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def _fmt(v, nd=1, suffix=""):
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return "—"
    return f"{v:,.{nd}f}{suffix}"


def _equity_reason(row):
    if row.get("data_suspect"):
        return f"**data suspect** — {row['price_breaks'][0]['looks_like']}"
    if row.get("insufficient_history"):
        return "insufficient price history"

    bits = []
    val = row.get("valuation") or {}
    if val.get("anchors_disagree"):
        d = val["disagreement"]
        bits.append(f"**anchors disagree** — {d['cheapest_anchor']} "
                    f"{d['cheapest_percentile']:.0f} vs {d['dearest_anchor']} "
                    f"{d['dearest_percentile']:.0f}")
    elif val.get("mean_percentile") is not None:
        bits.append(f"{val['valuation_label'].lower()} "
                    f"({_ordinal(val['mean_percentile'])} pct)")

    vs_ma = row.get("vs_ma_200_pct")
    if vs_ma is not None and not pd.isna(vs_ma):
        bits.append(f"{'above' if vs_ma > 0 else 'below'} 200d by {abs(vs_ma):.0f}%")
    return ", ".join(bits) if bits else "nothing notable"


def _etf_reason(row):
    etf = row.get("etf") or {}
    bits = []
    underlying = etf.get("underlying") or {}
    if underlying.get("label"):
        bits.append(underlying["label"])
    bits.extend(etf.get("structural_notes", []))
    if row.get("fx") and row["fx"] != "jpy":
        bits.append(row["fx"].replace("_", " "))
    return ", ".join(bits) if bits else "nothing notable"


def _equity_table(rows, add):
    add("## Equities")
    add("")
    add(f"Health is not built, so these carry {EQUITY_IMPLEMENTED}"
        f" of 10 points and no verdict.")
    add("")
    add("| Ticker | Name | Price | 12M | Valuation | Trend | Score | Verdict | Why |")
    add("| --- | --- | ---: | ---: | :-: | :-: | :-: | :-: | --- |")

    def partial(r):
        v = (r.get("valuation") or {}).get("valuation_score")
        t = r.get("trend_score")
        return None if (v is None and t is None) else (v or 0) + (t or 0)

    for r in sorted(rows, key=lambda r: (-(partial(r) or -1),
                                         -(r.get("return_12m_pct") or -999))):
        val = r.get("valuation") or {}
        vscore, trend, p = val.get("valuation_score"), r.get("trend_score"), partial(r)
        add(f"| {r['code']} | {universe_mod.display_name(r)} | "
            f"{_fmt(r.get('last_price'))} | {_fmt(r.get('return_12m_pct'), 0, '%')} | "
            f"{'—' if vscore is None else f'{vscore}/4'} | "
            f"{'—' if trend is None else f'{trend}/2'} | "
            f"{'—' if p is None else f'**{p}**/{EQUITY_IMPLEMENTED}'} | — | "
            f"{_equity_reason(r)} |")
    add("")


def _etf_table(rows, add):
    add("## ETFs")
    add("")
    add("A fund has no earnings, no book value and no business to be healthy, "
        "so none of the equity rubric applies. **Structure** replaces health: "
        "size and spread, the ways a fund fails its holder regardless of what "
        "it tracks. **Underlying** is the index multiple against a long-run "
        "reference declared in `config.py` — a judgement, not a fact.")
    add("")
    add("| Ticker | Name | Price | 12M | AUM ¥bn | Structure | Underlying | Trend | Score | Verdict | Why |")
    add("| --- | --- | ---: | ---: | ---: | :-: | :-: | :-: | :-: | :-: | --- |")

    for r in sorted(rows, key=lambda r: -(r.get("_etf_score") or -1)):
        etf = r.get("etf") or {}
        aum = (etf.get("profile") or {}).get("aum_jpy")
        structural = etf.get("structural_score")
        vscore = etf.get("valuation_score")
        trend = r.get("trend_score")
        score = r.get("_etf_score")
        add(f"| {r['code']} | {universe_mod.display_name(r)} | "
            f"{_fmt(r.get('last_price'))} | {_fmt(r.get('return_12m_pct'), 0, '%')} | "
            f"{_fmt(aum / 1e9, 0) if aum else '—'} | "
            f"{'—' if structural is None else f'{structural}/4'} | "
            f"{'—' if vscore is None else f'{vscore}/4'} | "
            f"{'—' if trend is None else f'{trend}/2'} | "
            f"{'—' if score is None else f'**{score}**/10'} | "
            f"**{r.get('_etf_verdict', '—')}** | {_etf_reason(r)} |")
    add("")
    add("*NAV premium and discount is reported in the run file but not scored "
        "— the feed does not timestamp NAV, so most apparent dislocation is a "
        "stale figure meeting a live price.*")
    add("")


def render(rows, as_of, prior=None):
    equities = [r for r in rows if r["asset_type"] == "Equity"]
    etfs = [r for r in rows if r["asset_type"] == "ETF"]
    suspect = [r for r in rows if r.get("data_suspect")]

    out = []
    add = out.append

    add(f"# Monthly Status Check — {as_of}")
    add("")
    add("> **⚠ PARTIAL RUN.** ETFs are fully scored and carry verdicts. "
        "Equities do not: the business health ladder is 4 of their 10 points "
        "and is the half that can reach SELL, so issuing equity calls now "
        "would mean issuing them from the half of the model that cannot say "
        "no. Everything shown is computed and real.")
    add("")
    add("# Market Score: not yet computed")
    add("")
    add("The five macro lenses are not built. When they are, this line carries "
        "one 0–10 number, its month-over-month arrow, and two sentences.")
    add("")
    add("---")
    add("")
    add("## Summary")
    add("")

    def vscore(r):
        return (r.get("valuation") or {}).get("valuation_score")

    dear = [r for r in equities if vscore(r) == 0]
    cheap = [r for r in equities if vscore(r) is not None and vscore(r) >= 3]
    disagree = [r for r in equities if (r.get("valuation") or {}).get("anchors_disagree")]
    trims = [r for r in etfs if r.get("_etf_verdict") == verdict_mod.TRIM]

    if suspect:
        add(f"- **{len(suspect)} price series unusable** — "
            f"{', '.join(r['code'] for r in suspect)}. Not scored, deliberately.")
    if dear:
        add(f"- **Dear against their own 5-year history:** "
            f"{', '.join(r['code'] for r in dear)}")
    if cheap:
        add(f"- **Cheap against their own history:** "
            f"{', '.join(r['code'] for r in cheap)}")
    if disagree:
        add(f"- **Anchors disagree** on {', '.join(r['code'] for r in disagree)} "
            f"— the mean describes none of them, so read the anchors, not the score.")
    if trims:
        add(f"- **Funds flagged TRIM:** {', '.join(r['code'] for r in trims)} "
            f"— sound vehicles, dear underlying index.")
    add("")
    add("---")
    add("")

    _equity_table(equities, add)
    add("---")
    add("")
    _etf_table(etfs, add)
    add("---")
    add("")

    add("### Still to build")
    add("")
    add("| Component | Score points |")
    add("| --- | :-: |")
    for _key, (label, points) in PENDING.items():
        add(f"| {label} | {points if points else '—'} |")
    add("")
    add(f"**The scale.** Soundness 0–4 + valuation 0–4 + trend 0–2. "
        f"**8–10 BUY · 4–7 KEEP · 0–3 SELL.** Soundness is health for an "
        f"equity and structure for a fund. TRIM overrides KEEP when the thing "
        f"is sound but its price is at an extreme. A name reporting within "
        f"{config.DEFER_DAYS_BEFORE_EARNINGS} days shows WAIT.")
    add("")

    corrected = [r for r in rows if r.get("corrections_applied")]
    if corrected:
        add("### Corrections applied")
        add("")
        add("Declared in `universe.toml`. The feed reported no split for either.")
        add("")
        for r in corrected:
            for act in r["corrections_applied"]:
                detail = (f"1:{act['ratio']:g} split, {act['sessions_rescaled']} "
                          f"sessions rescaled" if act["type"] == "split"
                          else "bad print dropped")
                add(f"- **{r['code']}** {act['date']} — {detail}")
        add("")

    add("---")
    add("")
    add(f"*Prices as of {as_of} close (JST). yfinance is a free, unofficial "
        f"feed; verify anything you act on against the filing. Not investment "
        f"advice — every threshold is a configurable assumption.*")
    return "\n".join(out) + "\n"


def _score_etfs(rows):
    """
    Funds have every component, so they get real verdicts now.

    Structure stands in for health, the underlying index multiple for
    valuation. A fund with no scorable index — a commodity trust, or one whose
    reported multiple was implausible — stays incomplete rather than being
    scored on the parts that happen to exist.
    """
    for row in rows:
        if row["asset_type"] != "ETF":
            continue
        etf = row.get("etf") or {}
        score = verdict_mod.total(etf.get("structural_score"),
                                  etf.get("valuation_score"),
                                  row.get("trend_score"))
        row["_etf_score"] = score
        row["_etf_verdict"] = verdict_mod.decide(
            score,
            soundness=etf.get("structural_score"),
            expensive_anchors=(config.TRIM_MIN_ANCHORS_EXPENSIVE
                               if etf.get("valuation_score") == config.TRIM_ETF_VALUATION_SCORE
                               else 0),
        )
    return rows


def main(argv=None):
    rows = indicators.build(keep_series=True)
    rows = valuation_mod.build(rows)
    rows = etf_mod.build(rows)
    _score_etfs(rows)
    dates = sorted({r["as_of"] for r in rows if r.get("as_of")})
    as_of = dates[-1] if dates else datetime.now().strftime("%Y-%m-%d")

    path = common.run_dir()
    common.save_json(os.path.join(path, "indicators.json"), rows)
    common.save_json(os.path.join(path, "run_meta.json"), {
        "as_of": as_of,
        "generated_at": common.utc_now(),
        "instruments": len(rows),
        "suspect": [r["code"] for r in rows if r.get("data_suspect")],
        "pending_components": sorted(PENDING),
        "score_points_implemented": IMPLEMENTED_POINTS,
        "score_points_total": TOTAL_POINTS,
    })

    md = render(rows, as_of)
    report_path = os.path.join(path, f"{as_of}-report.md")
    with open(report_path, "w") as fh:
        fh.write(md)

    print(md)
    print(f"\n→ {report_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
