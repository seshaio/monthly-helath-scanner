"""
The data pack: one frozen input, identical for every reviewer.

The pipeline computes; reviewers interpret a table they cannot edit. Each
model gets exactly this pack — same numbers, same order — so disagreement
between them is disagreement about meaning, never about what the price was.

Two deliberate exclusions:

  * No verdicts. The mechanical verdict is withheld so no reviewer anchors
    to it, and last month's calls are withheld so no reviewer herds toward
    its own history. The comparison happens afterwards, in consensus.py.
  * No news. Nothing in this pack is prose from the outside world, so
    nothing in it can smuggle in an instruction. If a reviewer knows news,
    it may use it — labelled as its own knowledge, not as pack data.
"""

import os
import sys

import common
import config
from monitor import universe as universe_mod

SCHEMA = """Reply with ONLY a JSON array, one object per ticker, no prose
around it:

[
  {
    "code": "8001",
    "verdict": "BUY | KEEP | TRIM | SELL | WAIT",
    "confidence": "high | medium | low",
    "rationale": "<= 50 words. Argue from the pack's numbers.",
    "red_flags": ["optional, only if you see one the data supports"]
  }
]

Rules: every ticker in the pack, exactly once. TRIM means sound but priced
at an extreme — reduce, not exit. SELL means the thing itself has
deteriorated. If you use knowledge beyond this pack, say so in the
rationale."""


def _fmt(value, nd=1):
    if value is None:
        return "null"
    return f"{value:.{nd}f}" if isinstance(value, float) else str(value)


def _equity_block(row):
    val = row.get("valuation") or {}
    health = row.get("health") or {}
    anchors = val.get("anchors") or {}
    lines = [
        f"### {row['code']} — {universe_mod.display_name(row)} (Equity)",
        f"- price {_fmt(row.get('last_price'))}, 12m {_fmt(row.get('return_12m_pct'))}%, "
        f"RSI {_fmt(row.get('rsi_14'))}, vs 200d {_fmt(row.get('vs_ma_200_pct'))}%",
        f"- valuation percentiles vs own 5y history (low=cheap): "
        + ", ".join(f"{name} {a['percentile']:.0f}" for name, a in anchors.items()),
        f"- health: {health.get('status')} — "
        + (f"{len(health.get('fired', []))} trigger(s): "
           + "; ".join(t["detail"] for t in health.get("fired", []))
           if health.get("fired") else "no trigger fired"),
    ]
    if val.get("anchors_disagree"):
        d = val["disagreement"]
        lines.append(f"- NOTE anchors disagree: {d['cheapest_anchor']} at "
                     f"{d['cheapest_percentile']:.0f} vs {d['dearest_anchor']} "
                     f"at {d['dearest_percentile']:.0f} — the mean describes neither")
    if health.get("marginal_trigger"):
        lines.append(f"- NOTE a trigger fired within a hair of its threshold: "
                     f"{health['marginal_trigger']['detail']}")
    tgt = row.get("targets") or {}
    if tgt.get("mean"):
        lines.append(f"- sell-side consensus (third-party, structurally "
                     f"bullish): mean {tgt['mean']:,.0f}, range "
                     f"{tgt.get('low', 0):,.0f}–{tgt.get('high', 0):,.0f}, "
                     f"n={tgt.get('analysts')}")
    if row.get("days_to_earnings") is not None and row["days_to_earnings"] >= 0:
        lines.append(f"- reports in {row['days_to_earnings']} days")
    return "\n".join(lines)


def _etf_block(row):
    etf = row.get("etf") or {}
    profile = etf.get("profile") or {}
    underlying = etf.get("underlying") or {}
    lines = [
        f"### {row['code']} — {universe_mod.display_name(row)} (ETF)",
        f"- price {_fmt(row.get('last_price'))}, 12m {_fmt(row.get('return_12m_pct'))}%, "
        f"RSI {_fmt(row.get('rsi_14'))}",
        f"- AUM ¥{profile.get('aum_jpy', 0) / 1e9:,.0f}bn, "
        f"spread {_fmt(etf.get('spread_pct'), 2)}%, fx: {row.get('fx')}",
        f"- underlying: {underlying.get('label')}",
    ]
    notes = etf.get("structural_notes") or []
    if notes:
        lines.append("- structural notes: " + "; ".join(notes))
    return "\n".join(lines)


def build(run_dir=None):
    """Render data_pack.md from a run's saved artifacts."""
    run_dir = run_dir or common.latest_run()
    if not run_dir:
        raise SystemExit("no run to pack — run the report first")
    rows = common.load_json(os.path.join(run_dir, "indicators.json"))
    macro = common.load_json(os.path.join(run_dir, "macro.json"))
    folio = common.load_json(os.path.join(run_dir, "portfolio.json"))

    out = [
        "# Monthly review data pack",
        "",
        "You are one of several independent reviewers of a fixed list of TSE "
        "instruments. Every number below was computed by the pipeline; none "
        "was retrieved by a model. Argue from these numbers. You are not "
        "shown any other reviewer's answer, any mechanical verdict, or any "
        "prior month's call — that is deliberate.",
        "",
        SCHEMA,
        "",
        "## Macro (lens scores are mechanical, −2 headwind to +2 tailwind)",
        "",
    ]
    for lens in macro["lenses"].values():
        out.append(f"- {lens['name']}: {lens['score']:+d} — {lens['basis']}"
                   if lens["score"] is not None else
                   f"- {lens['name']}: no data")
    out += ["", "## Portfolio (correlation, no weights)", ""]
    for cluster in folio.get("clusters", []):
        out.append(f"- cluster {', '.join(cluster['members'])}: mean pairwise "
                   f"ρ {cluster['mean_pairwise_rho']:.2f}")
    fx = folio.get("fx", {})
    for tag, codes in fx.items():
        out.append(f"- {tag}: {', '.join(codes)}")
    out += ["", "## Instruments", ""]
    for row in rows:
        if row.get("data_suspect"):
            out.append(f"### {row['code']} — price series unusable this month; "
                       f"reply WAIT with low confidence\n")
            continue
        out.append(_equity_block(row) if row["asset_type"] == "Equity"
                   else _etf_block(row))
        out.append("")
    return "\n".join(out) + "\n"


def main(argv=None):
    run_dir = common.latest_run()
    text = build(run_dir)
    path = os.path.join(run_dir, "data_pack.md")
    with open(path, "w") as fh:
        fh.write(text)
    print(text[:1200])
    print(f"...\n→ {path} ({len(text):,} chars)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
