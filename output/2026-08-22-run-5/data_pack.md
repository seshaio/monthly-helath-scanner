# Monthly review data pack

You are one of several independent reviewers of a fixed list of TSE instruments. Every number below was computed by the pipeline; none was retrieved by a model. Argue from these numbers. You are not shown any other reviewer's answer, any mechanical verdict, or any prior month's call — that is deliberate.

Reply with ONLY a JSON array, one object per ticker, no prose
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
rationale.

## Macro (lens scores are mechanical, −2 headwind to +2 tailwind)

- AI bubble: +0 — SOX -0.1% over 3m — neither breaking nor frothing
- War / geopolitics: +0 — WTI -10.5%, gold +1.2% over 3m — calm
- Japan domestic: +0 — TOPIX (via 1306) +4.7% over 3m [equity trend only — no JGB/CPI in this feed]
- US recession: +1 — 10y−13w +0.99pp, VIX 16 — positive curve, calm volatility
- USD/JPY: +1 — USD/JPY 159, +0.0% over 3m — stable, which is what this portfolio wants

## Portfolio (correlation, no weights)


## Instruments

### 7532 — Pan Pacific International Holdings Corporation (Equity)
- price 818.2, 12m -22.3%, RSI 36.2, vs 200d -10.6%
- valuation percentiles vs own 5y history (low=cheap): dividend_yield 0, ev_ebit 21, fcf_yield 28, pb 33, pe 41
- health: INTACT — no trigger fired
- sell-side consensus (third-party, structurally bullish): mean 1,067, range 900–1,300, n=17
- reports in 82 days

### 6383 — Daifuku Co., Ltd. (Equity)
- price 5900.0, 12m 50.6%, RSI 39.5, vs 200d -1.1%
- valuation percentiles vs own 5y history (low=cheap): dividend_yield 41, ev_ebit 62, fcf_yield 26, pb 82, pe 65
- health: INTACT — no trigger fired
- NOTE anchors disagree: fcf_yield at 26 vs pb at 82 — the mean describes neither
- sell-side consensus (third-party, structurally bullish): mean 7,541, range 5,400–9,300, n=14

### 8001 — ITOCHU Corporation (Equity)
- price 2080.0, 12m 35.0%, RSI 61.6, vs 200d 6.2%
- valuation percentiles vs own 5y history (low=cheap): dividend_yield 96, ev_ebit 91, fcf_yield 87, pb 84, pe 92
- health: INTACT — no trigger fired
- sell-side consensus (third-party, structurally bullish): mean 2,404, range 2,100–2,800, n=11
- reports in 74 days

### 8002 — Marubeni Corporation (Equity)
- price 4893.0, 12m 58.1%, RSI 44.5, vs 200d -2.7%
- valuation percentiles vs own 5y history (low=cheap): dividend_yield 89, ev_ebit 83, fcf_yield 87, pb 80, pe 87
- health: INTACT — no trigger fired
- sell-side consensus (third-party, structurally bullish): mean 6,068, range 5,100–7,180, n=12
- reports in 73 days

### 8053 — Sumitomo Corporation (Equity)
- price 1709.0, 12m 77.2%, RSI 53.3, vs 200d 13.5%
- valuation percentiles vs own 5y history (low=cheap): dividend_yield 96, ev_ebit 96, fcf_yield 53, pb 96, pe 95
- health: INTACT — no trigger fired
- sell-side consensus (third-party, structurally bullish): mean 1,963, range 1,660–2,263, n=10
- reports in 68 days

### 8031 — Mitsui & Co., Ltd. (Equity)
- price 4899.0, 12m 58.7%, RSI 53.9, vs 200d -3.2%
- valuation percentiles vs own 5y history (low=cheap): dividend_yield 88, ev_ebit 89, fcf_yield 95, pb 79, pe 89
- health: INTACT — no trigger fired
- sell-side consensus (third-party, structurally bullish): mean 6,162, range 4,500–7,600, n=13
- reports in 75 days

### 1944 — Kinden Corporation (Equity)
- price 6686.0, 12m 31.1%, RSI 39.8, vs 200d -6.8%
- valuation percentiles vs own 5y history (low=cheap): dividend_yield 74, ev_ebit 64, fcf_yield 20, pb 76, pe 63
- health: INTACT — no trigger fired
- NOTE anchors disagree: fcf_yield at 20 vs pb at 76 — the mean describes neither
- sell-side consensus (third-party, structurally bullish): mean 9,200, range 8,450–10,200, n=6
- reports in 68 days

### 2502 — Asahi Group Holdings, Ltd. (Equity)
- price 1680.5, 12m -9.6%, RSI 54.0, vs 200d 4.5%
- valuation percentiles vs own 5y history (low=cheap): dividend_yield 18, ev_ebit 99, fcf_yield 86, pb 14, pe 99
- health: IMPAIRED — 2 trigger(s): operating margin 6.4% vs 9.2% a year earlier (273bp fall); net debt / EBITDA 4.01x
- NOTE anchors disagree: pb at 14 vs pe at 99 — the mean describes neither
- NOTE a trigger fired within a hair of its threshold: net_debt_to_ebitda_above at 4.01 vs threshold 4.00
- sell-side consensus (third-party, structurally bullish): mean 2,052, range 1,670–2,700, n=15
- reports in 75 days

### 7974 — Nintendo Co., Ltd. (Equity)
- price 8599.0, 12m -36.1%, RSI 62.0, vs 200d -5.8%
- valuation percentiles vs own 5y history (low=cheap): dividend_yield 66, ev_ebit 46, fcf_yield 69, pb 30, pe 62
- health: WATCH — 1 trigger(s): operating margin 15.6% vs 24.3% a year earlier (869bp fall)
- sell-side consensus (third-party, structurally bullish): mean 10,335, range 5,000–21,260, n=25
- reports in 73 days

### 8766 — Tokio Marine Holdings, Inc. (Equity)
- price 7347.0, 12m 21.7%, RSI 39.7, vs 200d 10.7%
- valuation percentiles vs own 5y history (low=cheap): dividend_yield 69, pb 72, pe 84
- health: INTACT — no trigger fired
- sell-side consensus (third-party, structurally bullish): mean 8,601, range 5,842–10,500, n=12

### 7701 — Shimadzu Corporation (Equity)
- price 4109.0, 12m 27.0%, RSI 50.1, vs 200d 1.8%
- valuation percentiles vs own 5y history (low=cheap): dividend_yield 19, ev_ebit 21, fcf_yield 20, pb 16, pe 21
- health: INTACT — no trigger fired
- sell-side consensus (third-party, structurally bullish): mean 5,077, range 3,400–6,500, n=12
- reports in 75 days

### 4543 — Terumo Corporation (Equity)
- price 2569.0, 12m 2.9%, RSI 60.5, vs 200d 15.4%
- valuation percentiles vs own 5y history (low=cheap): dividend_yield 15, ev_ebit 21, fcf_yield 30, pb 17, pe 17
- health: INTACT — no trigger fired
- sell-side consensus (third-party, structurally bullish): mean 3,133, range 2,450–3,800, n=13

### 7269 — Suzuki Motor Corporation (Equity)
- price 2103.5, 12m 21.8%, RSI 57.0, vs 200d 1.5%
- valuation percentiles vs own 5y history (low=cheap): dividend_yield 44, ev_ebit 37, fcf_yield 21, pb 49, pe 23
- health: INTACT — no trigger fired
- sell-side consensus (third-party, structurally bullish): mean 2,568, range 1,800–3,300, n=17
- reports in 75 days

### 1540 — Japan Physical Gold ETF (ETF)
- price 21815.0, 12m 44.9%, RSI 68.2
- AUM ¥1,476bn, spread 0.05%, fx: usd_unhedged
- underlying: no earnings — commodity

### 315A — Global X Japan Bank High Dividend ETF (ETF)
- price 1873.0, 12m 81.0%, RSI 46.0
- AUM ¥24bn, spread 0.16%, fx: jpy
- underlying: index at 16.0x vs 13x reference (+23%) — scenario reference, declared 2026-08-21: BOJ normalization: policy rate 0.75% and rising; bank NIMs e…
- structural notes: AUM ¥24bn — modest; NAV premium not flagged — feed's navPrice verified unreliable for this fund, see universe.toml

### 1478 — iShares MSCI Japan High Dividend ETF (ETF)
- price 5311.0, 12m 36.7%, RSI 58.4
- AUM ¥148bn, spread 0.04%, fx: jpy
- underlying: index at 14.4x vs 13x reference (+11%)

### 2559 — MAXIS World Equity (MSCI ACWI) ETF (ETF)
- price 2997.0, 12m 34.0%, RSI 51.4
- AUM ¥128bn, spread 0.00%, fx: usd_unhedged
- underlying: index P/E 3.0 implausible — not scored

### 1655 — iShares S&P 500 ETF (ETF)
- price 876.1, 12m 31.8%, RSI 48.8
- AUM ¥182bn, spread 0.01%, fx: usd_unhedged
- underlying: index at 25.6x vs 18x reference (+42%)

### 1658 — iShares Core MSCI Emerging Markets IMI ETF (ETF)
- price 4400.0, 12m 48.3%, RSI 55.6
- AUM ¥29bn, spread 0.32%, fx: foreign_unhedged
- underlying: index at 17.1x vs 13x reference (+32%)
- structural notes: AUM ¥29bn — modest; spread 0.32% — wide

