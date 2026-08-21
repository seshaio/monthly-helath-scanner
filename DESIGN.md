# Monthly Status Check — design

A monthly monitor over a hand-picked list of TSE equities and ETFs.
Sibling to `../TSE-screener`, which is a *discovery* tool over the top 200.
This one is a *monitoring* tool over names already chosen.

**Not investment advice.** Every threshold here is a configurable assumption.

## The one principle

**Code computes the numbers. The LLM interprets a table it cannot edit.**

Every figure — price, RSI, valuation percentile, macro level — is computed once
by Python, frozen into a data pack, and handed identically to each model. The
LLM's job is judgement and narrative on top of fixed inputs, never retrieval.

This is why RSI is computed here and not asked for: a model that "looks up" a
14-day RSI returns a number of unknown date and unknown smoothing method, and
it differs between models. Disagreement between models must mean disagreement
about *meaning*, not about what the price was.

## Relationship to TSE-screener

Reads it, never imports it, never writes to it.

- `../TSE-screener/cache/info.json` — 525 Prime names with fundamentals.
  All 10 equities in the current universe hit; **no ETF does** (the screener
  seeds Prime domestic equities only). ETFs need their own fetch path.
- `../TSE-screener/output/latest/` — screen verdicts, for cross-reference:
  "this holding would/would not pass the discovery screen."

The screener's `monthly_run.sh` refuses to start if its source differs from
the last commit. Nothing here modifies that repo, so its guard stays intact.

## Universe — configurable

`universe.yaml`, the only file expected to change routinely:

```yaml
equities:
  - code: "7532"
    note: "core holding"
    held: true
  - code: "2502"
    held: true
etfs:
  - code: "1655"
    held: true
    fx: usd_unhedged          # drives portfolio FX exposure
  - code: "1540"
    held: true
    fx: usd_unhedged
```

Names are resolved from JPX's listed-issues workbook (the same source
`TSE-screener/config.py` already downloads) — never from a model's memory.
`held` distinguishes holdings from watchlist entries. Adding or removing a
ticker requires no code change.

Thresholds live in `config.py`, separate from the universe, so the *rules* hold
still while the *list* moves. A month where both changed is uninterpretable.

## Stages

```
monitor/
  universe.py     resolve codes -> names, types, from JPX workbook
  indicators.py   price, returns, RSI(14, Wilder), 200dma, realised vol,
                  drawdown, valuation percentiles vs own 5y history
  earnings.py     report dates; days since / days to; the staleness gate
  portfolio.py    correlation matrix, cluster detection, FX exposure
  macro.py        the fixed macro dashboard
  pack.py         -> data_pack.md + data_pack.json  (the frozen input)
  ingest.py       accept model verdict JSON back into the run folder
  consensus.py    agreement matrix across models; flags disagreements
  deltas.py       diff vs prior run; every verdict change carries its cause
  report.py       renders the report
  score.py        back-scores verdicts at 3 / 6 / 12 months vs TOPIX
  tripwire.py     the weekly between-runs check; silent unless something fires
```

Run folders follow the neighbour's convention: `output/YYYY-MM-DD-run-N/`,
with `output/latest` symlinked, so nothing is ever overwritten and two runs
can be diffed.

## Valuation — multi-anchor

Sell-side consensus is **one input, demoted**, always shown with its high/low
dispersion, never the deciding test. It is structurally bullish and revises
after prices move as often as before.

Primary anchors, each a percentile against the name's own 5-year history:

| Anchor | Why |
| --- | --- |
| P/E | conventional, but distorted by one-off gains |
| **P/B** | the Japan-specific one — TSE's sustained PBR<1 pressure |
| EV/EBIT | capital-structure neutral |
| FCF yield | hardest to manipulate |
| Dividend yield | the payout-policy signal |

Worked example of why P/B belongs: Asahi (2502) currently sits at P/B 0.81 —
below book. READ.md's original rubric has no P/B term at all and would score
that name purely on distance from an analyst target.

ETFs never take this rubric. They get: expense ratio, AUM and spread, tracking
difference, premium/discount to NAV, hedged vs unhedged, and the valuation of
the *underlying index*.

## Business health — graded, pre-committed

Binary FINE/BROKEN never fires until it is too late. Four steps, each with
observable triggers fixed in `config.py` *before* the data is seen:

- **INTACT** — no trigger fired
- **WATCH** — one trigger
- **IMPAIRED** — two, or any single severe trigger
- **BROKEN** — structural: fraud, restatement, going-concern, terminal decline

Triggers are things like: guidance cut twice running; operating margin down
>200bp YoY; FCF negative two consecutive years; auditor change or restatement;
covenant breach. The model may argue with a trigger, but may not un-fire it.

## Macro — anchored, not free-form

"Where are markets heading" written freehand produces fluent text driven by
whatever was in the news that week. Instead: a fixed dashboard of levels and
3-month changes — USD/JPY, JGB 10y and 2y, BOJ policy rate, US 10y, 2s10s,
VIX, TOPIX level and forward P/E, SOX, gold, Japan core CPI, US CPI.

The five standing lenses are scored the same way every month, each bound to
its indicators, on a fixed −2..+2 scale:

| Lens | Bound to |
| --- | --- |
| AI bubble | SOX, TOPIX AI-complex breadth, the screener's `AI_CORE` list |
| USD/JPY | spot, 3m change, rate differential, BOJ stance |
| US recession | 2s10s, claims, ISM, credit spreads |
| Japan domestic | core CPI, real wages, BOJ path, PBR reform pace |
| War / geopolitics | energy, shipping rates, defence budget moves |

Same lenses, same scale, every run — so month-over-month movement means
something. Regional read (US / Asia / EU) is derived from these, not asserted.

## Portfolio layer

Holdings are known; weights are not. So concentration is evidenced by
**realised correlation from price history**, which needs no weights:

- correlation matrix across the universe, 1y daily returns
- cluster detection — the current list holds four of the five sogo shosha
  (8001, 8002, 8031, 8053), which co-move on the same commodity/FX/China
  factors
- USD/JPY exposure: which names are structurally long USD (unhedged ETFs plus
  commodity-linked trading houses), reported as a count and a beta, not a
  weight

Sixteen independent per-name verdicts cannot surface any of this.

## The LLM panel

Primary reviewer is the agent in Claude Code, reading `data_pack.md` under a
fixed instruction file and emitting verdict JSON against a strict schema.
`data_pack.md` is also self-contained and paste-ready, so one or two external
chat models can be run by hand; `ingest.py` takes their JSON back.

Models are run **blind to last month's verdict**, so they do not herd. The
comparison happens afterwards, in code.

Verdicts are not averaged — averaging destroys the signal. `consensus.py`
builds an agreement matrix. Where models agree, accept and move on. Where they
disagree, that is the month's reading list.

News enters the pack as quoted data with source and date, clearly delimited.
It is never treated as instruction to the model.

## Report structure

**One page. One score, one table, one verdict per name.** If it does not help
answer buy / keep / sell, it does not print.

1. **Market Score** — the five macro lenses collapsed to a single 0–10 number,
   with its month-over-month arrow and two sentences of plain English.
2. **Summary** — at most four bullets. What to sell, what to watch, what is
   cheap, and any portfolio-level concentration worth knowing.
3. **The table** — all names, sorted by score descending. Columns: ticker,
   name, score, verdict, month-over-month change, and a short reason.
4. **Footer** — how the score is built, in four lines.

### Everything else still runs — it just doesn't print

This is the point. The full machinery computes on every run; the report is a
projection of it, not the whole of it. The detail lands in the run folder and
is read only when a flag sends you there.

| Computed every run | How it surfaces on the page |
| --- | --- |
| Health ladder + triggers | The health half of the score; `⚠` when a trigger fires |
| Five valuation anchors | The valuation half of the score |
| Consensus + dispersion | Feeds valuation only; never printed on its own |
| Correlation clusters, FX beta | One summary bullet, only when it changes |
| Model disagreement | `⚑` on the row — the month's reading item |
| Earnings calendar | Verdict shows `WAIT` instead of a stale score |
| Deltas vs last month | The `Δ` column |
| Scorecard | One line, and only once it has enough history to mean anything |

A number that never appears is still worth computing: it constrains the score,
and it is there when a flag makes you want it.

### Scoring — fixed before the data is fetched

| Component | Range |
| --- | :-: |
| Business health | 0–4 |
| Valuation vs own 5y history | 0–4 |
| Trend | 0–2 |

**8–10 BUY · 4–7 KEEP · 0–3 SELL.**

The band alone cannot express "healthy but expensive" — a 6 built from intact
health and a stretched multiple means something different from a 6 built from
a degraded business at fair value. So two overrides sit on top of it:

| Override | Condition | Meaning |
| --- | --- | --- |
| **TRIM** | Health INTACT **and** 4+ of 5 valuation anchors ≥ 85th percentile | Reduce, don't exit |
| **WAIT** | Reports within 5 days | Not scored this run |
| **SELL** | Health BROKEN | Always, however cheap |

Valuation alone never reaches SELL by score. Health scores 4 on its own, which
is the KEEP floor, so a sound business cannot be scored out on price — it can
only be trimmed. This is deliberate: expensive is a poor timing signal, and
"overvalued" here means dear against the name's *own* 5-year range, which a
genuinely improved business will breach and stay above.

Thresholds live in `config.py` and are set before any fetch, so the verdict
cannot be reasoned into a comfortable answer after the fact.

## Between runs

Monthly cadence means up to 30 days of blindness. A separate lightweight
tripwire runs weekly and only emails when something fires: price move beyond
a band, RSI extreme, earnings date approaching, guidance revision. The monthly
run is for thinking; the tripwire is what catches fires.

The run is also earnings-calendar aware: it tracks days since last report and
days to next, and says "defer, reports in 5 days" rather than reviewing a name
on stale figures.

## Traceability

Nine defects were identified in the original `READ.md` prompt. Each one maps to
a section above and to the module that implements it. A requirement with no
owning module is a requirement that does not get built.

| # | Defect in READ.md | Fix | Module |
| --- | --- | --- | --- |
| 1 | No memory between runs; no deltas | §4 of the report; verdict changes must name a cause | `deltas.py` |
| 2 | No feedback loop — verdicts never graded | §5 scorecard at 3/6/12m vs TOPIX | `score.py` |
| 3 | Valuation outsourced to sell-side consensus | Multi-anchor, consensus demoted | `indicators.py` |
| 4 | Binary FINE/BROKEN never fires in time | Four-step ladder, pre-committed triggers | `config.py` |
| 5 | ETFs judged on an equity rubric | Separate ETF rubric; equity terms never applied | `indicators.py` |
| 6 | No portfolio view; concentration invisible | Realised correlation, clusters, FX exposure | `portfolio.py` |
| 7 | Monthly cadence → up to 30 days blind | Weekly tripwire, silent unless fired | `tripwire.py` |
| 8 | Earnings-calendar blindness; stale reviews | Days since/to report; defer gate | `earnings.py` |
| 9 | Macro section is an unanchored essay | Fixed dashboard, five lenses on a −2..+2 scale | `macro.py` |

Two further items from the same review are folded in rather than listed:
model verdicts are collected blind and never averaged (`consensus.py`), and
news enters the pack as delimited data, never as instruction (`pack.py`).


## What this cannot see

Everything the screener cannot see — competitive position, management quality,
governance, customer concentration — plus two of its own: it inherits the
universe you chose, so it will never tell you about a name you did not list,
and it inherits yfinance's known unreliability on Japanese fundamentals. For
anything that matters, check the filing.
