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

- cluster 1655, 1658, 2559: mean pairwise ρ 0.77
- foreign_unhedged: 1658
- usd_unhedged: 1540, 2559, 1655

## Instruments

### 7532 — Pan Pacific International Holdings Corporation (Equity)
- price 812.9, 12m -22.8%, RSI 34.8, vs 200d -11.2%
- valuation percentiles vs own 5y history (low=cheap): dividend_yield 0, ev_ebit 19, fcf_yield 27, pb 31, pe 39
- health: INTACT — no trigger fired
- sell-side consensus (third-party, structurally bullish): mean 1,067, range 900–1,300, n=17
- reports in 83 days

### 6383 — Daifuku Co., Ltd. (Equity)
- price 5897.0, 12m 50.5%, RSI 39.4, vs 200d -1.2%
- valuation percentiles vs own 5y history (low=cheap): dividend_yield 41, ev_ebit 62, fcf_yield 26, pb 82, pe 65
- health: INTACT — no trigger fired
- NOTE anchors disagree: fcf_yield at 26 vs pb at 82 — the mean describes neither
- sell-side consensus (third-party, structurally bullish): mean 7,541, range 5,400–9,300, n=14

### 8001 — ITOCHU Corporation (Equity)
- price 2072.5, 12m 34.5%, RSI 60.8, vs 200d 5.8%
- valuation percentiles vs own 5y history (low=cheap): dividend_yield 95, ev_ebit 90, fcf_yield 86, pb 84, pe 92
- health: INTACT — no trigger fired
- sell-side consensus (third-party, structurally bullish): mean 2,404, range 2,100–2,800, n=11
- reports in 75 days

### 8002 — Marubeni Corporation (Equity)
- price 4906.0, 12m 58.5%, RSI 45.2, vs 200d -2.5%
- valuation percentiles vs own 5y history (low=cheap): dividend_yield 89, ev_ebit 84, fcf_yield 87, pb 81, pe 88
- health: INTACT — no trigger fired
- sell-side consensus (third-party, structurally bullish): mean 6,068, range 5,100–7,180, n=12
- reports in 74 days

### 8053 — Sumitomo Corporation (Equity)
- price 1718.5, 12m 78.2%, RSI 54.6, vs 200d 14.1%
- valuation percentiles vs own 5y history (low=cheap): dividend_yield 96, ev_ebit 97, fcf_yield 54, pb 97, pe 95
- health: INTACT — no trigger fired
- sell-side consensus (third-party, structurally bullish): mean 1,963, range 1,660–2,263, n=10
- reports in 69 days

### 8031 — Mitsui & Co., Ltd. (Equity)
- price 4893.0, 12m 58.5%, RSI 53.6, vs 200d -3.3%
- valuation percentiles vs own 5y history (low=cheap): dividend_yield 88, ev_ebit 89, fcf_yield 95, pb 79, pe 89
- health: INTACT — no trigger fired
- sell-side consensus (third-party, structurally bullish): mean 6,162, range 4,500–7,600, n=13
- reports in 76 days

### 1944 — Kinden Corporation (Equity)
- price 6671.0, 12m 30.8%, RSI 39.5, vs 200d -7.0%
- valuation percentiles vs own 5y history (low=cheap): dividend_yield 74, ev_ebit 64, fcf_yield 20, pb 76, pe 63
- health: INTACT — no trigger fired
- NOTE anchors disagree: fcf_yield at 20 vs pb at 76 — the mean describes neither
- sell-side consensus (third-party, structurally bullish): mean 9,200, range 8,450–10,200, n=6
- reports in 69 days

### 2502 — Asahi Group Holdings, Ltd. (Equity)
- price 1677.5, 12m -9.7%, RSI 53.6, vs 200d 4.3%
- valuation percentiles vs own 5y history (low=cheap): dividend_yield 18, ev_ebit 99, fcf_yield 87, pb 13, pe 99
- health: IMPAIRED — 2 trigger(s): operating margin 6.4% vs 9.2% a year earlier (273bp fall); net debt / EBITDA 4.01x
- NOTE anchors disagree: pb at 13 vs pe at 99 — the mean describes neither
- NOTE a trigger fired within a hair of its threshold: net_debt_to_ebitda_above at 4.01 vs threshold 4.00
- sell-side consensus (third-party, structurally bullish): mean 2,052, range 1,670–2,700, n=15
- reports in 76 days

### 7974 — Nintendo Co., Ltd. (Equity)
- price 8593.0, 12m -36.1%, RSI 61.9, vs 200d -5.8%
- valuation percentiles vs own 5y history (low=cheap): dividend_yield 66, ev_ebit 45, fcf_yield 69, pb 30, pe 62
- health: WATCH — 1 trigger(s): operating margin 15.6% vs 24.3% a year earlier (869bp fall)
- sell-side consensus (third-party, structurally bullish): mean 10,335, range 5,000–21,260, n=25
- reports in 74 days

### 8766 — Tokio Marine Holdings, Inc. (Equity)
- price 7372.0, 12m 22.1%, RSI 40.7, vs 200d 11.1%
- valuation percentiles vs own 5y history (low=cheap): dividend_yield 70, pb 72, pe 85
- health: INTACT — no trigger fired
- sell-side consensus (third-party, structurally bullish): mean 8,601, range 5,842–10,500, n=12

### 1540 — Japan Physical Gold ETF (ETF)
- price 21725.0, 12m 44.3%, RSI 67.4
- AUM ¥1,476bn, spread 0.05%, fx: usd_unhedged
- underlying: no earnings — commodity

### 315A — Global X Japan Bank High Dividend ETF (ETF)
- price 1879.0, 12m 81.6%, RSI 46.7
- AUM ¥24bn, spread 0.16%, fx: jpy
- underlying: index at 16.0x vs 13x reference (+23%) — scenario reference, declared 2026-08-21: BOJ normalization: policy rate 0.75% and rising; bank NIMs e…
- structural notes: AUM ¥24bn — modest; -3.7% vs NAV — larger than a stale NAV explains, worth a look

### 1478 — iShares MSCI Japan High Dividend ETF (ETF)
- price 5314.0, 12m 36.7%, RSI 58.5
- AUM ¥148bn, spread 0.04%, fx: jpy
- underlying: index at 14.4x vs 13x reference (+11%)

### 2559 — MAXIS World Equity (MSCI ACWI) ETF (ETF)
- price 2999.0, 12m 34.1%, RSI 51.8
- AUM ¥128bn, spread 0.00%, fx: usd_unhedged
- underlying: index P/E 3.0 implausible — not scored

### 1655 — iShares S&P 500 ETF (ETF)
- price 876.1, 12m 31.8%, RSI 48.8
- AUM ¥182bn, spread 0.01%, fx: usd_unhedged
- underlying: index at 25.6x vs 18x reference (+42%)

### 1658 — iShares Core MSCI Emerging Markets IMI ETF (ETF)
- price 4376.0, 12m 47.4%, RSI 54.3
- AUM ¥29bn, spread 0.32%, fx: foreign_unhedged
- underlying: index at 17.1x vs 13x reference (+32%)
- structural notes: AUM ¥29bn — modest; spread 0.32% — wide

