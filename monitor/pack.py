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
    "price_check": "match | differs | unchecked",
    "price_observed": null,
    "verdict": "BUY | KEEP | TRIM | SELL | WAIT",
    "confidence": "high | medium | low",
    "rationale": "<= 50 words. Argue from the pack's numbers.",
    "red_flags": ["optional, only if you see one the data supports"]
  }
]

Rules: every ticker in the pack, exactly once. TRIM means sound but priced
at an extreme — reduce, not exit. SELL means the thing itself has
deteriorated. If you use knowledge beyond this pack, say so in the
rationale.

PRICE CHECK — do this first, for every ticker. Each block below states the
price and the session it closed in ("price 2080.0 as of 2026-08-21 close").
The feed behind this pack has been caught serving a stale close under a
fresher date, so the price is the one number here you are asked to check
rather than accept:

  "match"     — the stated price is right for that name on that date.
  "differs"   — you have a different close for that date, or you know a
                later session has closed since. Put the price you believe in
                "price_observed" as a number, and name its date in the
                rationale.
  "unchecked" — you have no way to verify it. This is an honest answer; a
                guessed "match" is not.

Still argue your verdict from the pack's numbers even when you flag a
difference. The pack is identical for every reviewer so that disagreement
between you is disagreement about meaning — quietly substituting your own
price would destroy that. Flag it and reason from the pack; the divergence
is dealt with afterwards, in consensus."""


def _fmt(value, nd=1):
    if value is None:
        return "null"
    return f"{value:.{nd}f}" if isinstance(value, float) else str(value)


def _anchor_value(name, anchor):
    """
    The anchor's actual number, not just its rank.

    Ranks alone are what let a negative free cash flow yield read as an
    expensive price for a whole panel — every reviewer cited "fcf 95" as
    evidence the stock was dear, and none could see the number behind it
    was -1.11%. A percentile hides its own sign; the value does not.
    """
    value = anchor.get("value")
    if value is None:
        return "null"
    return f"{value:.2f}%" if anchor.get("inverted") else f"{value:.2f}"


def _equity_block(row):
    val = row.get("valuation") or {}
    health = row.get("health") or {}
    anchors = val.get("anchors") or {}
    lines = [
        f"### {row['code']} — {universe_mod.display_name(row)} (Equity)",
        f"- price {_fmt(row.get('last_price'))} as of {row.get('as_of') or 'unknown'} "
        f"close, 12m {_fmt(row.get('return_12m_pct'))}%, "
        f"RSI {_fmt(row.get('rsi_14'))}, vs 200d {_fmt(row.get('vs_ma_200_pct'))}%",
        f"- valuation vs own 5y history, percentile then value "
        f"(low percentile = cheap): "
        + ", ".join(f"{name} {a['percentile']:.0f} ({_anchor_value(name, a)})"
                    for name, a in anchors.items()),
        f"- health: {health.get('status')} — "
        + (f"{len(health.get('fired', []))} trigger(s): "
           + "; ".join(t["detail"] for t in health.get("fired", []))
           if health.get("fired") else "no trigger fired"),
    ]
    for name in val.get("negative_yield_anchors") or []:
        anchor = anchors[name]
        counted = name in (val.get("negative_yield_counted_expensive") or [])
        lines.append(
            f"- ⚠ NOTE {name} is NEGATIVE ({anchor['value']:.2f}%), so its "
            f"percentile of {anchor['percentile']:.0f} is not a valuation "
            f"reading. A negative yield does not mean the price is high; it "
            f"means there is no yield to price. The business changed, not the "
            f"multiple."
            + (" This anchor is nonetheless counted among the expensive ones, "
               "so treat any 'priced at an extreme' reading of this name with "
               "suspicion." if counted else ""))
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
        f"- price {_fmt(row.get('last_price'))} as of {row.get('as_of') or 'unknown'} "
        f"close, 12m {_fmt(row.get('return_12m_pct'))}%, "
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
    sessions = common.price_sessions(rows)

    out = [
        "# Monthly review data pack",
        "",
        "You are one of several independent reviewers of a fixed list of TSE "
        "instruments. Every number below was computed by the pipeline; none "
        "was retrieved by a model. Argue from these numbers. You are not "
        "shown any other reviewer's answer, any mechanical verdict, or any "
        "prior month's call — that is deliberate.",
        "",
    ]
    if sessions:
        out.append(
            f"**Prices as of {sessions[0][0]} close (JST)**, and every figure "
            f"derived from price — returns, RSI, distance to the 200d — is as "
            f"of that same session. Each instrument also carries its own "
            f"as-of date below; check it.")
        out.append("")
    if len(sessions) > 1:
        out.append(
            "**⚠ This pack mixes sessions.** The feed had not filled every "
            "name when the run started, so the instruments below are not all "
            "priced on the same day:")
        out.append("")
        for day, codes in sessions:
            out.append(f"- **{day}** — {len(codes)}: {', '.join(codes)}")
        out += [
            "",
            "The pack is stamped with the oldest of those dates. Treat the "
            "names on the older session as provisional: weigh them with lower "
            "confidence, and say in the rationale that the price is stale.",
            "",
        ]
    out += [
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
