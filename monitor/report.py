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


# Components not yet built. Each one contributes to the score, so while any
# is outstanding the score is partial and the verdict is withheld.
PENDING = {
    "valuation": ("valuation anchors vs own 5y history", 4),
    "health": ("business health ladder and triggers", 4),
    "macro": ("macro dashboard and the five lenses", None),
    "portfolio": ("correlation clusters and FX exposure", None),
    "earnings": ("earnings calendar and the defer gate", None),
}

IMPLEMENTED_POINTS = config.TREND_ABOVE_MA_POINTS + config.TREND_POSITIVE_12M_POINTS
TOTAL_POINTS = 10


def _reason(row):
    """A short, honest reason from price data alone."""
    if row.get("data_suspect"):
        return f"**data suspect** — {row['price_breaks'][0]['looks_like']}"
    if row.get("insufficient_history"):
        return "insufficient price history"

    bits = []
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


def _fmt(v, nd=1, suffix=""):
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return "—"
    return f"{v:,.{nd}f}{suffix}"


def render(rows, as_of, prior=None):
    """Render the page as markdown."""
    scored = [r for r in rows if not r.get("data_suspect")
              and not r.get("insufficient_history")]
    suspect = [r for r in rows if r.get("data_suspect")]

    out = []
    add = out.append

    add(f"# Monthly Status Check — {as_of}")
    add("")
    add("> **⚠ PARTIAL RUN — no verdicts.** "
        f"{IMPLEMENTED_POINTS} of {TOTAL_POINTS} score points are implemented "
        "(trend only). Health and valuation are the other 8 and are not built "
        "yet, so nothing here is a buy, keep or sell call. The table below is "
        "price behaviour, which is real, and nothing more.")
    add("")

    # --- Market score -----------------------------------------------------
    add("# Market Score: not yet computed")
    add("")
    add("The five macro lenses are not built. When they are, this line carries "
        "a single 0–10 number, its month-over-month arrow, and two sentences.")
    add("")
    add("---")
    add("")

    # --- Summary ----------------------------------------------------------
    add("## What the price data says")
    add("")
    if suspect:
        add(f"- **{len(suspect)} series unusable** — "
            f"{', '.join(r['code'] for r in suspect)}. Not scored, deliberately.")

    overbought = [r for r in scored if (r.get("rsi_14") or 0) >= 70]
    oversold = [r for r in scored if 0 < (r.get("rsi_14") or 100) <= 30]
    if overbought:
        add("- **Overbought on RSI:** "
            + ", ".join(f"{r['code']} ({r['rsi_14']:.0f})" for r in overbought))
    if oversold:
        add("- **Oversold on RSI:** "
            + ", ".join(f"{r['code']} ({r['rsi_14']:.0f})" for r in oversold))

    below = [r for r in scored if r.get("above_ma_200") is False]
    if below:
        add(f"- **Below the 200-day:** {', '.join(r['code'] for r in below)} "
            f"({len(below)} of {len(scored)})")

    worst = min(scored, key=lambda r: r.get("return_12m_pct") or 0, default=None)
    best = max(scored, key=lambda r: r.get("return_12m_pct") or 0, default=None)
    if best and worst:
        add(f"- **12-month spread:** {best['code']} "
            f"{best['return_12m_pct']:+.0f}% to {worst['code']} "
            f"{worst['return_12m_pct']:+.0f}%")
    add("")
    add("---")
    add("")

    # --- The table --------------------------------------------------------
    add("## The table")
    add("")
    add("Sorted by trend, then 12-month return. **Verdict is withheld** — it "
        "needs health and valuation.")
    add("")
    add("| Ticker | Name | Price | RSI | 12M | vs 200d | Trend | Verdict | Why |")
    add("| --- | --- | ---: | ---: | ---: | ---: | :-: | :-: | --- |")

    def sort_key(r):
        return (-(r.get("trend_score") if r.get("trend_score") is not None else -1),
                -(r.get("return_12m_pct") or -999))

    for r in sorted(rows, key=sort_key):
        trend = r.get("trend_score")
        add("| {code} | {name} | {price} | {rsi} | {r12} | {ma} | {trend} | {verdict} | {why} |".format(
            code=r["code"],
            name=universe_mod.display_name(r),
            price=_fmt(r.get("last_price")),
            rsi=_fmt(r.get("rsi_14"), 0),
            r12=_fmt(r.get("return_12m_pct"), 0, "%"),
            ma=_fmt(r.get("vs_ma_200_pct"), 0, "%"),
            trend="—" if trend is None else f"{trend}/2",
            verdict="—",
            why=_reason(r),
        ))
    add("")

    # --- Footer -----------------------------------------------------------
    add("---")
    add("")
    add("### Still to build")
    add("")
    add("| Component | Score points |")
    add("| --- | :-: |")
    for _key, (label, points) in PENDING.items():
        add(f"| {label} | {points if points else '—'} |")
    add("")
    add(f"**How the score will work.** Health 0–4 + valuation vs own 5-year "
        f"history 0–4 + trend 0–2. **8–10 BUY · 4–7 KEEP · 0–3 SELL.** TRIM "
        f"overrides KEEP when health is INTACT but "
        f"{config.TRIM_MIN_ANCHORS_EXPENSIVE}+ anchors sit at the "
        f"{config.TRIM_PERCENTILE}th percentile or above. A name reporting "
        f"within {config.DEFER_DAYS_BEFORE_EARNINGS} days shows WAIT.")
    add("")

    corrected = [r for r in rows if r.get("corrections_applied")]
    if corrected:
        add("### Corrections applied")
        add("")
        add("Declared in `universe.toml` and applied explicitly — the feed "
            "reported no split for either name.")
        add("")
        for r in corrected:
            for act in r["corrections_applied"]:
                detail = (f"1:{act['ratio']:g} split, {act['sessions_rescaled']} "
                          f"sessions rescaled" if act["type"] == "split"
                          else f"bad print dropped")
                add(f"- **{r['code']}** {act['date']} — {detail}")
        add("")

    add("---")
    add("")
    add(f"*Prices as of {as_of} close (JST). yfinance is a free, unofficial "
        f"feed; verify anything you act on against the filing. Not investment "
        f"advice — every threshold is a configurable assumption.*")
    return "\n".join(out) + "\n"


def main(argv=None):
    rows = indicators.build()
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
