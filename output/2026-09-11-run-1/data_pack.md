# Monthly review data pack

You are one of several independent reviewers of a fixed list of TSE instruments. Every number below was computed by the pipeline; none was retrieved by a model. Argue from these numbers. You are not shown any other reviewer's answer, any mechanical verdict, or any prior month's call — that is deliberate.

**Prices as of 2026-09-11 close (JST)**, and every figure derived from price — returns, RSI, distance to the 200d — is as of that same session. Each instrument also carries its own as-of date below; check it.

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

- AI bubble: -2 — SOX -10.0% over 3m while the S&P is up — the AI complex is rolling over without the market noticing yet
- War / geopolitics: +0 — WTI +12.8%, gold +8.3% over 3m — calm
- Japan domestic: +0 — TOPIX (via 1306) +3.8% over 3m [equity trend only — no JGB/CPI in this feed]
- US recession: +1 — 10y−13w +1.04pp, VIX 16 — positive curve, calm volatility
- USD/JPY: -1 — USD/JPY 153, -4.2% over 3m — yen firming against the unhedged USD exposure

## Portfolio (correlation, no weights)

- usd_unhedged: 1540, 2559

## Instruments

### 7532 — Pan Pacific International Holdings Corporation (Equity)
- price 726.1 as of 2026-09-11 close, 12m -31.2%, RSI 26.9, vs 200d -19.6%
- valuation vs own 5y history, percentile then value (low percentile = cheap): dividend_yield 0 (1.31%), ev_ebit 0 (17.08), fcf_yield 15 (3.67%), pb 5 (3.58), pe 16 (24.05)
- health: INTACT — no trigger fired
- sell-side consensus (third-party, structurally bullish): mean 1,052, range 900–1,300, n=17
- reports in 62 days

### 6383 — Daifuku Co., Ltd. (Equity)
- price 5429.0 as of 2026-09-11 close, 12m 17.3%, RSI 34.5, vs 200d -9.9%
- valuation vs own 5y history, percentile then value (low percentile = cheap): dividend_yield 21 (1.55%), ev_ebit 44 (17.24), fcf_yield 23 (5.55%), pb 75 (4.64), pe 51 (26.81)
- health: INTACT — no trigger fired
- NOTE anchors disagree: dividend_yield at 21 vs pb at 75 — the mean describes neither
- sell-side consensus (third-party, structurally bullish): mean 7,541, range 5,400–9,300, n=14
- reports in 60 days

### 8001 — ITOCHU Corporation (Equity)
- price 2294.0 as of 2026-09-11 close, 12m 39.7%, RSI 74.4, vs 200d 15.5%
- valuation vs own 5y history, percentile then value (low percentile = cheap): dividend_yield 99 (1.83%), ev_ebit 99 (15.55), fcf_yield 96 (5.25%), pb 91 (2.45), pe 99 (17.92)
- health: INTACT — no trigger fired
- sell-side consensus (third-party, structurally bullish): mean 2,452, range 2,100–2,800, n=11
- reports in 54 days

### 8002 — Marubeni Corporation (Equity)
- price 5049.0 as of 2026-09-11 close, 12m 52.9%, RSI 50.9, vs 200d -1.4%
- valuation vs own 5y history, percentile then value (low percentile = cheap): dividend_yield 91 (2.13%), ev_ebit 86 (13.78), fcf_yield 91 (4.55%), pb 83 (1.92), pe 90 (18.08)
- health: INTACT — no trigger fired
- sell-side consensus (third-party, structurally bullish): mean 5,994, range 5,100–7,100, n=12
- reports in 53 days

### 8053 — Sumitomo Corporation (Equity)
- price 1822.0 as of 2026-09-11 close, 12m 81.0%, RSI 56.9, vs 200d 17.2%
- valuation vs own 5y history, percentile then value (low percentile = cheap): dividend_yield 99 (2.06%), ev_ebit 99 (15.59), fcf_yield 57 (8.06%), pb 98 (1.90), pe 98 (14.62)
- health: INTACT — no trigger fired
- sell-side consensus (third-party, structurally bullish): mean 1,972, range 1,660–2,300, n=10
- reports in 48 days

### 8031 — Mitsui & Co., Ltd. (Equity)
- price 5060.0 as of 2026-09-11 close, 12m 51.2%, RSI 53.6, vs 200d -1.7%
- valuation vs own 5y history, percentile then value (low percentile = cheap): dividend_yield 90 (2.27%), ev_ebit 91 (15.06), fcf_yield 92 (-1.07%), pb 82 (1.65), pe 90 (17.40)
- health: INTACT — no trigger fired
- ⚠ NOTE fcf_yield is NEGATIVE (-1.07%), so its percentile of 92 is not a valuation reading. A negative yield does not mean the price is high; it means there is no yield to price. The business changed, not the multiple. This anchor is nonetheless counted among the expensive ones, so treat any 'priced at an extreme' reading of this name with suspicion.
- sell-side consensus (third-party, structurally bullish): mean 6,109, range 4,500–7,600, n=12
- reports in 55 days

### 1944 — Kinden Corporation (Equity)
- price 6756.0 as of 2026-09-11 close, 12m 30.9%, RSI 42.2, vs 200d -6.8%
- valuation vs own 5y history, percentile then value (low percentile = cheap): dividend_yield 74 (1.92%), ev_ebit 65 (13.16), fcf_yield 23 (6.55%), pb 75 (2.02), pe 63 (19.27)
- health: INTACT — no trigger fired
- NOTE anchors disagree: fcf_yield at 23 vs pb at 75 — the mean describes neither
- sell-side consensus (third-party, structurally bullish): mean 9,292, range 8,450–10,200, n=6
- reports in 48 days

### 2502 — Asahi Group Holdings, Ltd. (Equity)
- price 1586.5 as of 2026-09-11 close, 12m -11.7%, RSI 36.8, vs 200d -1.3%
- valuation vs own 5y history, percentile then value (low percentile = cheap): dividend_yield 7 (3.28%), ev_ebit 90 (18.58), fcf_yield 92 (-2.10%), pb 8 (0.79), pe 92 (19.52)
- health: IMPAIRED — 2 trigger(s): operating margin 6.4% vs 9.2% a year earlier (273bp fall); net debt / EBITDA 4.01x
- ⚠ NOTE fcf_yield is NEGATIVE (-2.10%), so its percentile of 92 is not a valuation reading. A negative yield does not mean the price is high; it means there is no yield to price. The business changed, not the multiple. This anchor is nonetheless counted among the expensive ones, so treat any 'priced at an extreme' reading of this name with suspicion.
- NOTE anchors disagree: dividend_yield at 7 vs fcf_yield at 92 — the mean describes neither
- NOTE a trigger fired within a hair of its threshold: net_debt_to_ebitda_above at 4.01 vs threshold 4.00
- sell-side consensus (third-party, structurally bullish): mean 2,056, range 1,670–2,700, n=15
- reports in 55 days

### 7974 — Nintendo Co., Ltd. (Equity)
- price 8093.0 as of 2026-09-11 close, 12m -37.8%, RSI 41.9, vs 200d -8.0%
- valuation vs own 5y history, percentile then value (low percentile = cheap): dividend_yield 57 (2.71%), ev_ebit 37 (13.41), fcf_yield 67 (2.79%), pb 23 (3.19), pe 58 (22.20)
- health: WATCH — 1 trigger(s): operating margin 15.6% vs 24.3% a year earlier (869bp fall)
- sell-side consensus (third-party, structurally bullish): mean 10,523, range 5,000–21,260, n=25
- reports in 53 days

### 8766 — Tokio Marine Holdings, Inc. (Equity)
- price 7970.0 as of 2026-09-11 close, 12m 28.6%, RSI 59.1, vs 200d 17.4%
- valuation vs own 5y history, percentile then value (low percentile = cheap): dividend_yield 82 (2.74%), pb 84 (1.91), pe 95 (28.55)
- health: INTACT — no trigger fired
- sell-side consensus (third-party, structurally bullish): mean 8,601, range 5,842–10,500, n=12
- reports in 69 days

### 7701 — Shimadzu Corporation (Equity)
- price 3742.0 as of 2026-09-11 close, 12m 5.2%, RSI 28.0, vs 200d -6.9%
- valuation vs own 5y history, percentile then value (low percentile = cheap): dividend_yield 10 (1.84%), ev_ebit 2 (11.31), fcf_yield 6 (3.68%), pb 1 (1.91), pe 2 (17.87)
- health: INTACT — no trigger fired
- sell-side consensus (third-party, structurally bullish): mean 5,093, range 3,400–6,500, n=12
- reports in 56 days

### 4543 — Terumo Corporation (Equity)
- price 2246.0 as of 2026-09-11 close, 12m -14.6%, RSI 33.4, vs 200d 1.0%
- valuation vs own 5y history, percentile then value (low percentile = cheap): dividend_yield 8 (1.34%), ev_ebit 8 (18.80), fcf_yield 13 (3.89%), pb 3 (2.09), pe 3 (24.38)
- health: INTACT — no trigger fired
- sell-side consensus (third-party, structurally bullish): mean 3,141, range 2,450–3,800, n=13
- reports in 61 days

### 7269 — Suzuki Motor Corporation (Equity)
- price 2047.0 as of 2026-09-11 close, 12m 6.2%, RSI 47.7, vs 200d -0.8%
- valuation vs own 5y history, percentile then value (low percentile = cheap): dividend_yield 37 (2.25%), ev_ebit 30 (4.90), fcf_yield 17 (7.44%), pb 40 (1.17), pe 20 (8.99)
- health: INTACT — no trigger fired
- sell-side consensus (third-party, structurally bullish): mean 2,609, range 1,800–3,300, n=17
- reports in 60 days

### 1540 — Japan Physical Gold ETF (ETF)
- price 20050.0 as of 2026-09-11 close, 12m 33.0%, RSI 38.7
- AUM ¥1,630bn, spread 0.10%, fx: usd_unhedged
- underlying: no earnings — commodity

### 315A — Global X Japan Bank High Dividend ETF (ETF)
- price 1963.0 as of 2026-09-11 close, 12m 74.2%, RSI 54.2
- AUM ¥25bn, spread 0.05%, fx: jpy
- underlying: index at 15.4x vs 13x reference (+18%) — scenario reference, declared 2026-08-21: BOJ normalization: policy rate 0.75% and rising; bank NIMs e…
- structural notes: AUM ¥25bn — modest; NAV premium not flagged — feed's navPrice verified unreliable for this fund, see universe.toml

### 1478 — iShares MSCI Japan High Dividend ETF (ETF)
- price 5319.0 as of 2026-09-11 close, 12m 31.9%, RSI 51.9
- AUM ¥153bn, spread 0.19%, fx: jpy
- underlying: index at 14.0x vs 13x reference (+8%)

### 2559 — MAXIS World Equity (MSCI ACWI) ETF (ETF)
- price 2893.0 as of 2026-09-11 close, 12m 26.1%, RSI 29.6
- AUM ¥136bn, spread 0.03%, fx: usd_unhedged
- underlying: index P/E 2.9 implausible — not scored

### 1655 — iShares S&P 500 ETF (ETF)
- price 846.2 as of 2026-09-11 close, 12m 24.4%, RSI 30.4
- AUM ¥193bn, spread 0.02%, fx: usd_unhedged
- underlying: index at 23.6x vs 18x reference (+31%)

### 1658 — iShares Core MSCI Emerging Markets IMI ETF (ETF)
- price 4250.0 as of 2026-09-11 close, 12m 41.3%, RSI 43.5
- AUM ¥31bn, spread 0.59%, fx: foreign_unhedged
- underlying: index at 13.8x vs 13x reference (+6%)
- structural notes: AUM ¥31bn — modest; spread 0.59% — exit costs bite

