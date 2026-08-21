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
from monitor import health as health_mod
from monitor import macro as macro_mod
from monitor import portfolio as portfolio_mod
from monitor import earnings as earnings_mod
from monitor import deltas as deltas_mod
from monitor import score as score_mod
from monitor import verdict as verdict_mod


# Components not yet built. Each one contributes to the score, so while any
# is outstanding the score is partial and the verdict is withheld.
PENDING = {
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


def _buy_floor():
    """The lowest score that reads BUY, derived from the bands."""
    keep_ceiling = [c for c, v in config.VERDICT_BANDS if v == "KEEP"][0]
    return keep_ceiling + 1


def near_buy(rows):
    """
    Names one point below BUY, with the missing trigger stated as a distance.

    Mechanical distances, not predictions: "cross the 200d, 1% below" says
    what would flip the score, and nothing about whether it will happen.
    Only names whose soundness is already full qualify — a name that is one
    point short because its health slipped is not "nearly a BUY".
    """
    target = _buy_floor() - 1
    out = []
    for r in rows:
        etf = r["asset_type"] == "ETF"
        score = r.get("_etf_score") if etf else r.get("_score")
        soundness = ((r.get("etf") or {}).get("structural_score") if etf
                     else (r.get("health") or {}).get("health_score"))
        if score != target or soundness is None or soundness < 4:
            continue

        hints = []
        if (r.get("trend_score") or 0) < 2:
            vs = r.get("vs_ma_200_pct")
            if vs is not None and vs < 0:
                hints.append(f"cross the 200d ({abs(vs):.0f}% below)")
            r12 = r.get("return_12m_pct")
            if r12 is not None and r12 < 0:
                hints.append("12m return turning positive as old declines "
                             "age out of the window")
        if not etf:
            val = r.get("valuation") or {}
            vscore = val.get("valuation_score")
            mean = val.get("mean_percentile")
            if vscore is not None and vscore < 4 and mean is not None and not hints:
                edge = [c for c, sc in config.VALUATION_BANDS if sc == vscore + 1][0]
                hints.append(f"valuation easing below the {edge}th pct "
                             f"(now {mean:.0f}th)")
        else:
            under = (r.get("etf") or {}).get("underlying") or {}
            ratio = under.get("ratio")
            if ratio is not None and not hints:
                edges = [c for c, sc in config.ETF_VALUATION_BANDS
                         if sc == (under.get("score") or 0) + 1]
                if edges:
                    hints.append(f"underlying at {ratio:.2f}× reference; "
                                 f"≤{edges[0]:.2f}× gains the point")
        if hints:
            out.append((r["code"], " or ".join(hints)))
    return out


def _delta_cell(row, delta_map):
    """The month-over-month movement for one name."""
    if not delta_map:
        return "*first run*"
    delta = delta_map.get(row["code"])
    if delta is None or delta.get("new"):
        return "new"
    if delta.get("verdict_changed"):
        return f"**was {delta['previous_verdict']}**"
    change = delta.get("score_change")
    if change:
        return f"{change:+d}"
    return "—"


def _target_cell(row):
    """Consensus mean with implied move. Demoted: shown, never scored."""
    tgt = row.get("targets") or {}
    mean, price = tgt.get("mean"), row.get("last_price")
    if not mean or not price:
        return "—"
    implied = (mean / price - 1) * 100
    return f"{mean:,.0f} ({implied:+.0f}%)"


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


def _equity_table(rows, add, delta_map):
    add("## Equities")
    add("")
    add("**Health** is the ladder: INTACT, WATCH, IMPAIRED, BROKEN. Its "
        "triggers are fixed in `config.py` before any data is fetched, and a "
        "trigger can be argued with but not un-fired. **Buy ≤ / Sell ≥** is a "
        "one-sigma monthly band from the name's own realised volatility, "
        "rounded to valid TSE ticks — a statistical band for limit orders, "
        "not a forecast; it says nothing about direction. **12M Tgt** is the "
        "sell-side consensus mean — third-party opinion, shown with its "
        "high/low range in the run file, and it does not score.")
    add("")
    add("| Ticker | Name | Price | Buy ≤ | Sell ≥ | 12M | 12M Tgt | Health | Valuation | Trend | Score | Verdict | Δ | Why |")
    add("| --- | --- | ---: | ---: | ---: | ---: | ---: | :-: | :-: | :-: | :-: | :-: | :-: | --- |")

    for r in sorted(rows, key=lambda r: (-(r.get("_score") or -1),
                                         -(r.get("return_12m_pct") or -999))):
        val = r.get("valuation") or {}
        health = r.get("health") or {}
        hscore, vscore = health.get("health_score"), val.get("valuation_score")
        trend, score = r.get("trend_score"), r.get("_score")
        health_cell = ("—" if hscore is None
                       else f"{health['status']} {hscore}/4")
        add(f"| {r['code']} | {universe_mod.display_name(r)} | "
            f"{_fmt(r.get('last_price'))} | "
            f"{_fmt(r.get('buy_limit_1m'), 0)} | "
            f"{_fmt(r.get('sell_limit_1m'), 0)} | "
            f"{_fmt(r.get('return_12m_pct'), 0, '%')} | "
            f"{_target_cell(r)} | "
            f"{health_cell} | "
            f"{'—' if vscore is None else f'{vscore}/4'} | "
            f"{'—' if trend is None else f'{trend}/2'} | "
            f"{'—' if score is None else f'**{score}**/10'} | "
            f"**{r.get('_verdict', '—')}** | {_delta_cell(r, delta_map)} | "
            f"{_equity_reason(r)} |")
    add("")


def _etf_table(rows, add, delta_map):
    add("## ETFs")
    add("")
    add("A fund has no earnings, no book value and no business to be healthy, "
        "so none of the equity rubric applies. **Structure** replaces health: "
        "size and spread, the ways a fund fails its holder regardless of what "
        "it tracks. **Underlying** is the index multiple against a long-run "
        "reference declared in `config.py` — a judgement, not a fact.")
    add("")
    add("| Ticker | Name | Price | Buy ≤ | Sell ≥ | 12M | AUM ¥bn | Structure | Underlying | Trend | Score | Verdict | Δ | Why |")
    add("| --- | --- | ---: | ---: | ---: | ---: | ---: | :-: | :-: | :-: | :-: | :-: | :-: | --- |")

    for r in sorted(rows, key=lambda r: -(r.get("_etf_score") or -1)):
        etf = r.get("etf") or {}
        aum = (etf.get("profile") or {}).get("aum_jpy")
        structural = etf.get("structural_score")
        vscore = etf.get("valuation_score")
        trend = r.get("trend_score")
        score = r.get("_etf_score")
        add(f"| {r['code']} | {universe_mod.display_name(r)} | "
            f"{_fmt(r.get('last_price'))} | "
            f"{_fmt(r.get('buy_limit_1m'), 0)} | "
            f"{_fmt(r.get('sell_limit_1m'), 0)} | "
            f"{_fmt(r.get('return_12m_pct'), 0, '%')} | "
            f"{_fmt(aum / 1e9, 0) if aum else '—'} | "
            f"{'—' if structural is None else f'{structural}/4'} | "
            f"{'—' if vscore is None else f'{vscore}/4'} | "
            f"{'—' if trend is None else f'{trend}/2'} | "
            f"{'—' if score is None else f'**{score}**/10'} | "
            f"**{r.get('_etf_verdict', '—')}** | {_delta_cell(r, delta_map)} | "
            f"{_etf_reason(r)} |")
    add("")
    add("*NAV premium and discount is reported in the run file but not scored "
        "— the feed does not timestamp NAV, so most apparent dislocation is a "
        "stale figure meeting a live price.*")
    add("")


def render(rows, as_of, macro=None, folio=None, delta_map=None,
           scorecard=None, previous_run_name=None):
    equities = [r for r in rows if r["asset_type"] == "Equity"]
    etfs = [r for r in rows if r["asset_type"] == "ETF"]
    suspect = [r for r in rows if r.get("data_suspect")]

    out = []
    add = out.append

    add(f"# Monthly Status Check — {as_of}")
    add("")
    add("> Verdicts are the mechanical output of thresholds fixed before the "
        "data was fetched — a starting point for reading, not a conclusion.")
    add("")

    if macro and macro.get("market_score") is not None:
        add(f"# Market Score: {macro['market_score']}/10 — {macro['market_label']}")
        add("")
        lenses = {k: l for k, l in macro["lenses"].items()
                  if l["score"] is not None}
        if lenses:
            worst = min(lenses.values(), key=lambda l: l["score"])
            best = max(lenses.values(), key=lambda l: l["score"])
            add(f"{worst['basis'].rstrip('.')}. {best['basis'].rstrip('.')}.")
        add("")
        add("| Lens | Score | Basis |")
        add("| --- | :-: | --- |")
        for lens in macro["lenses"].values():
            score_cell = "—" if lens["score"] is None else f"{lens['score']:+d}"
            add(f"| {lens['name']} | {score_cell} | {lens['basis']} |")
        add("")
        add("<details><summary>Dashboard</summary>")
        add("")
        add("| Indicator | Level | 3m Δ |")
        add("| --- | ---: | ---: |")
        for name, row in macro["dashboard"].items():
            lvl = "—" if row["level"] is None else f"{row['level']:,.2f}"
            chg = "—" if row["chg_3m_pct"] is None else f"{row['chg_3m_pct']:+.1f}%"
            add(f"| {name} | {lvl} | {chg} |")
        add("")
        add("</details>")
        add("")
    else:
        add("# Market Score: not computed — a macro feed failed")
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
    trims = ([r for r in etfs if r.get("_etf_verdict") == verdict_mod.TRIM]
             + [r for r in equities if r.get("_verdict") == verdict_mod.TRIM])

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
    impaired = [r for r in equities
                if (r.get("health") or {}).get("status")
                in (config.HEALTH_IMPAIRED, config.HEALTH_BROKEN)]
    watch = [r for r in equities
             if (r.get("health") or {}).get("status") == config.HEALTH_WATCH]
    sells = [r for r in rows if r.get("_verdict") == verdict_mod.SELL
             or r.get("_etf_verdict") == verdict_mod.SELL]

    waits = [r for r in rows if r.get("_verdict") == verdict_mod.WAIT]
    if sells:
        add(f"- **SELL:** {', '.join(r['code'] for r in sells)}")
    if waits:
        add(f"- **WAIT:** " + ", ".join(
            f"{r['code']} (reports in {r['days_to_earnings']}d)" for r in waits))
    knife_edge = [r for r in equities if (r.get("health") or {}).get("marginal_trigger")]
    if knife_edge:
        add(f"- **Balanced on a threshold:** "
            + ", ".join(r["code"] for r in knife_edge)
            + " — a trigger fired within a hair of its cut-off, so the verdict "
              "would change if it had not. See the triggers section.")
    if impaired:
        add(f"- **Health impaired:** " + ", ".join(
            f"{r['code']} ({len(r['health']['fired'])} triggers)" for r in impaired))
    if watch:
        add(f"- **Health on watch:** " + ", ".join(
            f"{r['code']} ({r['health']['fired'][0]['trigger']})" for r in watch))
    if trims:
        add(f"- **TRIM:** {', '.join(r['code'] for r in trims)} — sound, but "
            f"priced at an extreme. Reduce, not exit.")
    nearly = near_buy(rows)
    if nearly:
        add(f"- **One point from BUY:** " + "; ".join(
            f"{code} — {hint}" for code, hint in nearly)
            + ". Distances, not predictions.")
    add("")
    add("---")
    add("")

    _equity_table(equities, add, delta_map)
    add("---")
    add("")
    _etf_table(etfs, add, delta_map)
    add("---")
    add("")

    if folio:
        add("## Portfolio")
        add("")
        add("Correlation over the trailing year, from price history — no "
            "position sizes involved. Names that move together are one bet "
            "however many lines they occupy.")
        add("")
        for cluster in folio.get("clusters", []):
            add(f"- **Cluster:** {', '.join(cluster['members'])} — mean "
                f"pairwise ρ {cluster['mean_pairwise_rho']:.2f}. Effectively "
                f"one position held {len(cluster['members'])} ways.")
        pairs = folio.get("top_pairs", [])
        if pairs:
            add(f"- **Tightest pairs:** " + "; ".join(
                f"{a}/{b} ρ {rho:.2f}" for a, b, rho in pairs[:3]))
        fx = folio.get("fx", {})
        if fx:
            parts = [f"{len(codes)} {tag.replace('_', ' ')} ({', '.join(codes)})"
                     for tag, codes in fx.items()]
            add(f"- **Non-yen exposure by tag:** {'; '.join(parts)}. Counts, "
                f"not weights — the tags say how many names carry it, not how "
                f"much.")
        add("")
        add("---")
        add("")

    changed = [code for code, d in (delta_map or {}).items()
               if not d.get("new") and d.get("verdict_changed")]
    if delta_map and previous_run_name:
        add(f"## Changes since {previous_run_name}")
        add("")
        if not changed:
            add("No verdict changed.")
        for code in changed:
            delta = delta_map[code]
            row = next((r for r in rows if r["code"] == code), {})
            now = row.get("_verdict") or row.get("_etf_verdict")
            causes = "; ".join(
                f"{c['component']}: {c['from']} → {c['to']}"
                for c in delta.get("causes", [])) or "no component moved — check thresholds"
            add(f"- **{code}: {delta['previous_verdict']} → {now}.** Cause: {causes}.")
        add("")
        add("---")
        add("")

    add("## Scorecard")
    add("")
    if scorecard:
        insufficient = [f"{h}m" for h, v in sorted(scorecard.items())
                        if not v["sufficient"]]
        for horizon, summary in sorted(scorecard.items()):
            if summary["sufficient"]:
                add(f"- **{horizon}-month:** {summary['graded']} graded, "
                    f"hit rate {summary['hit_rate']:.0%}, median excess "
                    f"{summary['median_excess_pct']:+.1f}pp vs TOPIX")
        if insufficient:
            add(f"- Insufficient history at {', '.join(insufficient)} — a hit "
                f"rate needs {config.SCORECARD_MIN_VERDICTS}+ graded calls "
                f"before it stops being a coin-flip. Logging started with "
                f"this run's verdicts.")
    add("")
    add("---")
    add("")

    fired_rows = [r for r in equities if (r.get("health") or {}).get("fired")]
    if fired_rows:
        add("### Health triggers fired")
        add("")
        for r in fired_rows:
            health = r["health"]
            add(f"**{r['code']} {universe_mod.display_name(r)} — "
                f"{health['status']}**")
            for t in health["fired"]:
                flag = " *(marginal)*" if t.get("marginal") else ""
                add(f"- {t['detail']}{flag}")
            marginal = health.get("marginal_trigger")
            if marginal:
                add("")
                add(f"  > ⚠ **This verdict rests on a hair.** {marginal['detail']}. "
                    f"Without it the name would read {marginal['would_be']}, and "
                    f"the verdict would change. The threshold is not wrong — but "
                    f"a call balanced on it is worth checking against the filing "
                    f"before acting.")
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


def _score_equities(rows):
    """Health + valuation + trend, then the overrides."""
    for row in rows:
        if row["asset_type"] != "Equity":
            continue
        health = row.get("health") or {}
        val = row.get("valuation") or {}
        score = verdict_mod.total(health.get("health_score"),
                                  val.get("valuation_score"),
                                  row.get("trend_score"))
        row["_score"] = score
        row["_verdict"] = verdict_mod.decide(
            score,
            soundness=health.get("health_score"),
            expensive_anchors=val.get("anchors_expensive", 0),
            broken=health.get("status") == config.HEALTH_BROKEN,
            days_to_earnings=row.get("days_to_earnings"),
        )
    return rows


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
    rows = health_mod.build(rows)
    rows = earnings_mod.build(rows)
    _score_etfs(rows)
    _score_equities(rows)
    macro = macro_mod.build()
    folio = portfolio_mod.build(rows)
    dates = sorted({r["as_of"] for r in rows if r.get("as_of")})
    as_of = dates[-1] if dates else datetime.now().strftime("%Y-%m-%d")

    path = common.run_dir()
    previous_verdicts, previous_run_name = deltas_mod.load_previous(path)

    verdicts = {"_benchmark_level": (macro["dashboard"].get("topix") or {}).get("level")}
    for r in rows:
        etf = r["asset_type"] == "ETF"
        verdicts[r["code"]] = {
            "verdict": r.get("_etf_verdict") if etf else r.get("_verdict"),
            "score": r.get("_etf_score") if etf else r.get("_score"),
            "price": r.get("last_price"),
            "health_status": (r.get("health") or {}).get("status"),
            "valuation_score": ((r.get("etf") or {}).get("valuation_score") if etf
                                else (r.get("valuation") or {}).get("valuation_score")),
            "structural_score": (r.get("etf") or {}).get("structural_score"),
            "trend_score": r.get("trend_score"),
        }
    common.save_json(os.path.join(path, "verdicts.json"), verdicts)

    delta_map = (deltas_mod.compare(
        {k: v for k, v in verdicts.items() if not k.startswith("_")},
        previous_verdicts and {k: v for k, v in previous_verdicts.items()
                               if not k.startswith("_")})
        if previous_verdicts else None)

    prices_now = {r["code"]: r.get("last_price") for r in rows}
    scorecard = score_mod.summarise(score_mod.grade(
        prices_now, verdicts["_benchmark_level"]))

    common.save_json(os.path.join(path, "macro.json"), macro)
    common.save_json(os.path.join(path, "portfolio.json"), folio)
    common.save_json(os.path.join(path, "indicators.json"), rows)
    common.save_json(os.path.join(path, "run_meta.json"), {
        "as_of": as_of,
        "generated_at": common.utc_now(),
        "instruments": len(rows),
        "suspect": [r["code"] for r in rows if r.get("data_suspect")],
        "market_score": macro.get("market_score"),
    })

    md = render(rows, as_of, macro=macro, folio=folio, delta_map=delta_map,
                scorecard=scorecard, previous_run_name=previous_run_name)
    report_path = os.path.join(path, f"{as_of}-report.md")
    with open(report_path, "w") as fh:
        fh.write(md)

    print(md)
    print(f"\n→ {report_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
