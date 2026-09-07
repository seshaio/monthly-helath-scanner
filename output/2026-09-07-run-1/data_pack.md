# Monthly review data pack

You are one of several independent reviewers of a fixed list of TSE instruments. Every number below was computed by the pipeline; none was retrieved by a model. Argue from these numbers. You are not shown any other reviewer's answer, any mechanical verdict, or any prior month's call — that is deliberate.

**Prices as of 2026-09-04 close (JST)**, and every figure derived from price — returns, RSI, distance to the 200d — is as of that same session. Each instrument also carries its own as-of date below; check it.

Reply with ONLY a JSON array, one object per ticker, no prose
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
is dealt with afterwards, in consensus.

## Macro (lens scores are mechanical, −2 headwind to +2 tailwind)

- AI bubble: +0 — SOX -4.0% over 3m — neither breaking nor frothing
- War / geopolitics: +0 — WTI +0.2%, gold +3.2% over 3m — calm
- Japan domestic: +1 — TOPIX (via 1306) +7.5% over 3m — a real uptrend [equity trend only — no JGB/CPI in this feed]
- US recession: +1 — 10y−13w +1.03pp, VIX 15 — positive curve, calm volatility
- USD/JPY: +1 — USD/JPY 156, -2.8% over 3m — stable, which is what this portfolio wants

## Portfolio (correlation, no weights)

- usd_unhedged: 1540, 2559

## Instruments

### 7532 — Pan Pacific International Holdings Corporation (Equity)
- price 776.2 as of 2026-09-04 close, 12m -28.7%, RSI 34.0, vs 200d -14.5%
- valuation vs own 5y history, percentile then value (low percentile = cheap): dividend_yield 0 (1.22%), ev_ebit 4 (18.13), fcf_yield 21 (3.43%), pb 20 (3.83), pe 33 (25.71)
- health: INTACT — no trigger fired
- sell-side consensus (third-party, structurally bullish): mean 1,052, range 900–1,300, n=17
- reports in 66 days

### 6383 — Daifuku Co., Ltd. (Equity)
- price 5661.0 as of 2026-09-04 close, 12m 23.7%, RSI 36.8, vs 200d -5.8%
- valuation vs own 5y history, percentile then value (low percentile = cheap): dividend_yield 31 (1.48%), ev_ebit 56 (18.05), fcf_yield 24 (5.32%), pb 77 (4.83), pe 59 (27.95)
- health: INTACT — no trigger fired
- NOTE anchors disagree: fcf_yield at 24 vs pb at 77 — the mean describes neither
- sell-side consensus (third-party, structurally bullish): mean 7,576, range 5,400–9,300, n=14
- reports in 64 days

### 8001 — ITOCHU Corporation (Equity)
- price 2204.0 as of 2026-09-04 close, 12m 38.0%, RSI 69.8, vs 200d 11.5%
- valuation vs own 5y history, percentile then value (low percentile = cheap): dividend_yield 99 (1.91%), ev_ebit 97 (15.07), fcf_yield 91 (5.46%), pb 89 (2.35), pe 98 (17.22)
- health: INTACT — no trigger fired
- sell-side consensus (third-party, structurally bullish): mean 2,452, range 2,100–2,800, n=11
- reports in 58 days

### 8002 — Marubeni Corporation (Equity)
- price 5073.0 as of 2026-09-04 close, 12m 57.2%, RSI 53.5, vs 200d -0.3%
- valuation vs own 5y history, percentile then value (low percentile = cheap): dividend_yield 91 (2.12%), ev_ebit 87 (13.84), fcf_yield 91 (4.53%), pb 84 (1.93), pe 91 (18.17)
- health: INTACT — no trigger fired
- sell-side consensus (third-party, structurally bullish): mean 5,994, range 5,100–7,100, n=12
- reports in 57 days

### 8053 — Sumitomo Corporation (Equity)
- price 1820.0 as of 2026-09-04 close, 12m 84.3%, RSI 59.9, vs 200d 18.3%
- valuation vs own 5y history, percentile then value (low percentile = cheap): dividend_yield 99 (2.06%), ev_ebit 99 (15.57), fcf_yield 57 (8.07%), pb 99 (1.89), pe 98 (14.60)
- health: INTACT — no trigger fired
- sell-side consensus (third-party, structurally bullish): mean 1,972, range 1,660–2,300, n=10
- reports in 52 days

### 8031 — Mitsui & Co., Ltd. (Equity)
- price 5019.0 as of 2026-09-04 close, 12m 53.4%, RSI 53.4, vs 200d -2.0%
- valuation vs own 5y history, percentile then value (low percentile = cheap): dividend_yield 90 (2.29%), ev_ebit 91 (14.96), fcf_yield 93 (-1.08%), pb 81 (1.64), pe 90 (17.26)
- health: INTACT — no trigger fired
- ⚠ NOTE fcf_yield is NEGATIVE (-1.08%), so its percentile of 93 is not a valuation reading. A negative yield does not mean the price is high; it means there is no yield to price. The business changed, not the multiple. This anchor is nonetheless counted among the expensive ones, so treat any 'priced at an extreme' reading of this name with suspicion.
- sell-side consensus (third-party, structurally bullish): mean 6,092, range 4,500–7,600, n=12
- reports in 59 days

### 1944 — Kinden Corporation (Equity)
- price 7047.0 as of 2026-09-04 close, 12m 34.5%, RSI 50.1, vs 200d -2.5%
- valuation vs own 5y history, percentile then value (low percentile = cheap): dividend_yield 79 (1.84%), ev_ebit 71 (13.75), fcf_yield 38 (6.28%), pb 80 (2.11), pe 69 (20.10)
- health: INTACT — no trigger fired
- sell-side consensus (third-party, structurally bullish): mean 9,292, range 8,450–10,200, n=6
- reports in 52 days

### 2502 — Asahi Group Holdings, Ltd. (Equity)
- price 1639.0 as of 2026-09-04 close, 12m -11.6%, RSI 45.5, vs 200d 1.9%
- valuation vs own 5y history, percentile then value (low percentile = cheap): dividend_yield 12 (3.17%), ev_ebit 95 (18.96), fcf_yield 89 (-2.03%), pb 11 (0.82), pe 95 (20.16)
- health: IMPAIRED — 2 trigger(s): operating margin 6.4% vs 9.2% a year earlier (273bp fall); net debt / EBITDA 4.01x
- ⚠ NOTE fcf_yield is NEGATIVE (-2.03%), so its percentile of 89 is not a valuation reading. A negative yield does not mean the price is high; it means there is no yield to price. The business changed, not the multiple. This anchor is nonetheless counted among the expensive ones, so treat any 'priced at an extreme' reading of this name with suspicion.
- NOTE anchors disagree: pb at 11 vs pe at 95 — the mean describes neither
- NOTE a trigger fired within a hair of its threshold: net_debt_to_ebitda_above at 4.01 vs threshold 4.00
- sell-side consensus (third-party, structurally bullish): mean 2,056, range 1,670–2,700, n=15
- reports in 59 days

### 7974 — Nintendo Co., Ltd. (Equity)
- price 8839.0 as of 2026-09-04 close, 12m -34.3%, RSI 59.5, vs 200d -0.9%
- valuation vs own 5y history, percentile then value (low percentile = cheap): dividend_yield 68 (2.48%), ev_ebit 50 (14.94), fcf_yield 69 (2.55%), pb 35 (3.48), pe 64 (24.25)
- health: WATCH — 1 trigger(s): operating margin 15.6% vs 24.3% a year earlier (869bp fall)
- sell-side consensus (third-party, structurally bullish): mean 10,487, range 5,000–21,260, n=25
- reports in 57 days

### 8766 — Tokio Marine Holdings, Inc. (Equity)
- price 7976.0 as of 2026-09-04 close, 12m 25.4%, RSI 62.0, vs 200d 18.4%
- valuation vs own 5y history, percentile then value (low percentile = cheap): dividend_yield 82 (2.73%), pb 84 (1.91), pe 95 (28.57)
- health: INTACT — no trigger fired
- sell-side consensus (third-party, structurally bullish): mean 8,601, range 5,842–10,500, n=12
- reports in 73 days

### 7701 — Shimadzu Corporation (Equity)
- price 3846.0 as of 2026-09-04 close, 12m 6.0%, RSI 33.0, vs 200d -4.7%
- valuation vs own 5y history, percentile then value (low percentile = cheap): dividend_yield 15 (1.79%), ev_ebit 6 (11.67), fcf_yield 11 (3.58%), pb 5 (1.97), pe 8 (18.37)
- health: INTACT — no trigger fired
- sell-side consensus (third-party, structurally bullish): mean 5,085, range 3,400–6,500, n=12
- reports in 60 days

### 4543 — Terumo Corporation (Equity)
- price 2432.0 as of 2026-09-04 close, 12m -10.0%, RSI 45.8, vs 200d 9.1%
- valuation vs own 5y history, percentile then value (low percentile = cheap): dividend_yield 12 (1.23%), ev_ebit 17 (20.31), fcf_yield 23 (3.59%), pb 13 (2.26), pe 13 (26.40)
- health: INTACT — no trigger fired
- sell-side consensus (third-party, structurally bullish): mean 3,141, range 2,450–3,800, n=13
- reports in 65 days

### 7269 — Suzuki Motor Corporation (Equity)
- price 2067.0 as of 2026-09-04 close, 12m 6.6%, RSI 47.6, vs 200d -0.1%
- valuation vs own 5y history, percentile then value (low percentile = cheap): dividend_yield 40 (2.23%), ev_ebit 32 (4.95), fcf_yield 18 (7.36%), pb 42 (1.18), pe 22 (9.08)
- health: INTACT — no trigger fired
- sell-side consensus (third-party, structurally bullish): mean 2,609, range 1,800–3,300, n=17
- reports in 64 days

### 1540 — Japan Physical Gold ETF (ETF)
- price 20930.0 as of 2026-09-04 close, 12m 40.8%, RSI 49.0
- AUM ¥1,476bn, spread 0.02%, fx: usd_unhedged
- underlying: no earnings — commodity

### 315A — Global X Japan Bank High Dividend ETF (ETF)
- price 1990.0 as of 2026-09-04 close, 12m 78.1%, RSI 59.4
- AUM ¥24bn, spread 0.10%, fx: jpy
- underlying: index at 17.0x vs 13x reference (+31%) — scenario reference, declared 2026-08-21: BOJ normalization: policy rate 0.75% and rising; bank NIMs e…
- structural notes: AUM ¥24bn — modest; NAV premium not flagged — feed's navPrice verified unreliable for this fund, see universe.toml

### 1478 — iShares MSCI Japan High Dividend ETF (ETF)
- price 5387.0 as of 2026-09-04 close, 12m 33.7%, RSI 57.6
- AUM ¥148bn, spread 0.07%, fx: jpy
- underlying: index at 14.6x vs 13x reference (+12%)

### 2559 — MAXIS World Equity (MSCI ACWI) ETF (ETF)
- price 2980.0 as of 2026-09-04 close, 12m 31.5%, RSI 45.1
- AUM ¥128bn, spread 0.07%, fx: usd_unhedged
- underlying: index P/E 3.0 implausible — not scored

### 1655 — iShares S&P 500 ETF (ETF)
- price 872.6 as of 2026-09-04 close, 12m 29.6%, RSI 45.1
- AUM ¥182bn, spread 0.01%, fx: usd_unhedged
- underlying: index at 25.3x vs 18x reference (+41%)

### 1658 — iShares Core MSCI Emerging Markets IMI ETF (ETF)
- price 4360.0 as of 2026-09-04 close, 12m 44.7%, RSI 51.2
- AUM ¥29bn, spread 0.41%, fx: foreign_unhedged
- underlying: index at 17.2x vs 13x reference (+33%)
- structural notes: AUM ¥29bn — modest; spread 0.41% — exit costs bite

