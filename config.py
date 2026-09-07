"""
Every threshold and judgement call, in one place.

These are set *before* any data is fetched. That is the whole point: a score
computed against thresholds chosen after seeing the data is not a measurement,
it is a rationalisation. If you want to move one, move it deliberately, note
why, and expect that month's comparison with the previous month to be void.

Nothing here is a recommendation. These are the knobs on a rules-based
monitor.
"""

# --------------------------------------------------------------------------
# Where things live
# --------------------------------------------------------------------------

UNIVERSE_FILE = "universe.toml"
OUTPUT_DIR = "output"
CACHE_DIR = "cache"
CACHE_TTL_HOURS = 24

# The sibling screener. Read-only — this project never writes there.
# Its cache already holds fundamentals for ~525 Prime names, which covers the
# equities in this universe (but no ETF: it seeds domestic equities only).
SIBLING_DIR = "../TSE-screener"
SIBLING_INFO_CACHE = SIBLING_DIR + "/cache/info.json"

JPX_LISTED_ISSUES_URL = (
    "https://www.jpx.co.jp/markets/statistics-equities/misc/"
    "tvdivq0000001vg2-att/data_j.xlsx"
)

# --------------------------------------------------------------------------
# Fetching
# --------------------------------------------------------------------------
# Yahoo throttles on request rate. Sixteen names is small enough that this is
# never the bottleneck, so the delay is generous rather than tuned. Do not
# lower it to make a run faster — on the sibling project that is exactly what
# once produced a silently wrong report.

REQUEST_DELAY_SECONDS = 0.35
MAX_WORKERS = 4
MAX_RETRIES = 3
RETRY_BACKOFF_SECONDS = 2.0

# --------------------------------------------------------------------------
# Price history and technicals
# --------------------------------------------------------------------------

HISTORY_YEARS = 5              # valuation percentiles need the full window

# Price history is cached for same-day re-runs only. It is never extended
# incrementally: auto-adjusted prices change retroactively every time a
# dividend is paid, so appending fresh days onto saved old days produces a
# series that diverges silently from what a clean fetch would return. A full
# monthly refetch is one batched call for the whole universe — cheap, and
# always internally consistent.
PRICE_CACHE_TTL_HOURS = 24
RSI_PERIOD = 14                # Wilder's smoothing, not simple MA
MOVING_AVERAGE_DAYS = 200
VOLATILITY_WINDOW_DAYS = 252
CORRELATION_WINDOW_DAYS = 252

# A price series shorter than this cannot support the indicators, so the name
# is reported as insufficient-history rather than scored on a partial window.
MIN_TRADING_DAYS = 200

# --------------------------------------------------------------------------
# Session settlement
# --------------------------------------------------------------------------
# The feed starts emitting a bar the moment the session opens and keeps
# revising it after the bell. Measured on 2026-08-21: a run at 13:30 JST read
# 8001 at 2068.5, a run at 15:56 (26 minutes after the close) read 2072.5,
# and the settled close was 2080.0. Nothing in the numbers says which of the
# three you are holding — an unsettled bar is not a close, and scoring one
# prices the portfolio mid-session under a header claiming otherwise.
#
# So a bar is used only once its session has settled. Japan does not observe
# DST, so a fixed offset is correct year-round.
JST_UTC_OFFSET_HOURS = 9
TSE_CLOSE_JST = (15, 30)       # regular session close

# How long after the bell a daily bar is trusted as final. The true lag is
# not known: 26 minutes was observed still moving, the next morning was
# settled, and nothing narrows it further. This is a floor, not a guarantee —
# the real backstop is that per-instrument as-of dates are reported rather
# than collapsed, so a bar that is late or missing is visible in the report
# instead of being averaged into it.
SETTLE_MINUTES_AFTER_CLOSE = 90

# --------------------------------------------------------------------------
# Price-series integrity
# --------------------------------------------------------------------------
# Found on the first live run: 2559 fell 90% in a day on an unrecorded 1:10
# split, then 90% again on a bad print. The feed reported no split, so
# auto_adjust did nothing and five years of history sat on the wrong scale.
# Unguarded, that name reads as -86% over 12 months and scores SELL on trend.
#
# A move this large in one session is not a market event in a large-cap or a
# broad ETF. It is a corporate action the feed missed, or a bad tick. Either
# way the series cannot be scored, and the name is reported as suspect rather
# than quietly carrying a fabricated collapse into the report.

MAX_PLAUSIBLE_DAILY_MOVE_PCT = 35.0

# Ratios close to these are almost certainly splits rather than price moves.
COMMON_SPLIT_RATIOS = (1.5, 2, 2.5, 3, 4, 5, 10, 20, 100)
SPLIT_RATIO_TOLERANCE = 0.06

# Suspect series are never auto-repaired. Rescaling history silently is how a
# wrong report gets produced with full confidence; the break is surfaced and
# the correction is a deliberate human act, recorded in universe.toml.
AUTO_REPAIR_SPLITS = False

# Distinguishing a split from a bad print: look at the sessions after the
# break. A split holds the new scale; a bad print snaps back to the old one.
BREAK_LOOKAHEAD_SESSIONS = 5
BREAK_RECOVERY_TOLERANCE = 0.15

# --------------------------------------------------------------------------
# Business health — the ladder
# --------------------------------------------------------------------------
# Binary FINE/BROKEN never fires until it is too late, so health is graded and
# every step is tied to something observable. A trigger can be argued with in
# the write-up; it cannot be un-fired.

HEALTH_INTACT = "INTACT"
HEALTH_WATCH = "WATCH"
HEALTH_IMPAIRED = "IMPAIRED"
HEALTH_BROKEN = "BROKEN"

# One trigger -> WATCH. Two -> IMPAIRED. Any severe trigger -> IMPAIRED alone.
HEALTH_TRIGGERS = {
    "operating_margin_drop_bp": 200,      # YoY fall, basis points
    "revenue_decline_pct": -5.0,          # YoY
    "fcf_negative_consecutive_years": 2,
    "net_debt_to_ebitda_above": 4.0,
    "roe_below_pct": 3.0,
}

# Severe on their own: these are structural, not cyclical.
HEALTH_SEVERE_TRIGGERS = {
    "auditor_change",
    "restatement",
    "going_concern_doubt",
    "covenant_breach",
    "guidance_cut_twice_running",
}

# Leverage measured against EBITDA is meaningless when deposits and reserves
# are raw material rather than borrowing, so financials skip that trigger for
# the same reason they skip EV/EBIT.
FINANCIAL_EXCLUDED_HEALTH_TRIGGERS = ("net_debt_to_ebitda_above",)

# Severe events cannot be computed from a price feed — they live in filings
# and disclosures. They are declared by hand in universe.toml, verified
# against the issuer, exactly like a corporate action.
#
# A severe trigger alone reaches IMPAIRED. BROKEN is never inferred: calling
# a business structurally broken is a judgement a human makes deliberately,
# so it needs its own explicit declaration.
HEALTH_BROKEN_TRIGGERS = {"going_concern_doubt", "fraud"}

# At least this many annual periods, or health is reported as unassessed
# rather than computed from a single year with nothing to compare against.
HEALTH_MIN_PERIODS = 2

# And at least this many of the five triggers must actually be testable.
# Silence from a field the feed never returned is not a clean bill of health,
# so a name with too little to test on is reported unassessed and gets no
# verdict, rather than defaulting to INTACT because nothing could fire.
HEALTH_MIN_TRIGGERS_TESTED = 3

# A trigger that fires this close to its threshold is flagged as marginal.
# Asahi on the first live run fired the leverage trigger at 4.01x against a
# 4.0x threshold — and that single hundredth was the difference between WATCH
# and IMPAIRED, which was the difference between KEEP and SELL. The threshold
# is not wrong; a verdict balanced on it just has to say so out loud.
HEALTH_MARGINAL_BAND_PCT = 5.0

HEALTH_SCORE = {
    HEALTH_INTACT: 4,
    HEALTH_WATCH: 2,
    HEALTH_IMPAIRED: 1,
    HEALTH_BROKEN: 0,
}

# --------------------------------------------------------------------------
# Valuation — multi-anchor, each vs the name's OWN history
# --------------------------------------------------------------------------
# Percentile against its own 5-year range, not against the market and not
# against an absolute notion of fair value. A name can sit at its own 5-year
# high because the business genuinely improved.
#
# Consensus targets are deliberately absent from this table. They are fetched
# and shown, but they do not score: they are structurally bullish and revise
# after prices move as often as before.

VALUATION_ANCHORS = ("pe", "pb", "ev_ebit", "fcf_yield", "dividend_yield")

# For yield-style anchors a HIGH value is cheap, so the percentile is inverted
# before scoring. Getting this backwards is the easiest silent bug here.
VALUATION_ANCHORS_INVERTED = ("fcf_yield", "dividend_yield")

# An inverted anchor can go negative, and the inversion then says the exact
# opposite of what it means: a negative free cash flow yield ranks at the
# bottom of its own history, inverts to "dear", and reads as an expensive
# price. Mitsui (8031) shipped that way — +671bn of free cash flow became
# -155bn, health did not fire because its trigger needs two consecutive
# years, and all three panel reviewers cited "fcf 95" as proof the stock was
# richly priced. The rank was right; nothing about the price had moved.
#
# The fix is disclosure, not arithmetic: these are the underlying annual
# figures to print beside the rank so the turn is visible.
YIELD_ANCHOR_DRIVERS = {"fcf_yield": "fcf", "dividend_yield": "dividends"}

# Mean percentile across available anchors -> valuation score 0-4.
# Low percentile = cheap against its own history = high score.
VALUATION_BANDS = [
    (20, 4),      # <=20th pct: cheapest fifth of its own 5y range
    (40, 3),
    (60, 2),
    (80, 1),
    (101, 0),     # >80th pct: dearest fifth
]

# At least this many anchors must be available, or valuation is unscored and
# the name is reported as partial rather than scored on one number.
VALUATION_MIN_ANCHORS = 3

# An anchor needs this much daily history before its percentile means
# anything. A rank computed from a handful of observations is noise wearing a
# decimal point.
VALUATION_MIN_OBSERVATIONS = 250

# Results are published weeks after the fiscal period closes. Applying a
# figure from the period-end date would let a historical run "know" earnings
# before the market did, which flatters every percentile it computes.
# Japanese issuers file full-year results within 45 days of year end.
FUNDAMENTALS_PUBLICATION_LAG_DAYS = 45

VALUATION_LABELS = {
    4: "CHEAP vs own history",
    3: "BELOW its own average",
    2: "MID-RANGE",
    1: "ABOVE its own average",
    0: "DEAR vs own history",
}

# Banks and insurers. Enterprise value and free cash flow are not meaningful
# when deposits and reserves are raw material rather than leverage, so those
# anchors are skipped rather than computed on a broken definition. The sibling
# screener drops financials outright for the same reason; this project holds
# them, so it scores them on the anchors that do apply.
FINANCIAL_CODES = {"8766", "315A"}
FINANCIAL_EXCLUDED_ANCHORS = ("ev_ebit", "fcf_yield")

# When anchors disagree by more than this many percentile points, the mean is
# not a summary of them — it is a number that describes none of them. Asahi on
# the first live run: P/E at the 99th percentile because earnings fell 36%,
# P/B at the 13th because equity kept growing. The average of those, 63, is
# the one reading that is certainly wrong. Flag it instead of hiding it.
VALUATION_DISPERSION_THRESHOLD = 50

# --------------------------------------------------------------------------
# Trend
# --------------------------------------------------------------------------
# Deliberately small (0-2). It is there to break ties between names of similar
# health and valuation, not to drive the verdict.

TREND_ABOVE_MA_POINTS = 1
TREND_POSITIVE_12M_POINTS = 1

# --------------------------------------------------------------------------
# One-month limit band
# --------------------------------------------------------------------------
# A mechanical band for placing limit orders: one monthly standard deviation
# around the last price, from the name's own 1-year realised volatility.
# Statistics, not prediction — if volatility stays put, roughly two months in
# three close inside the band. It says nothing about direction.
#
# Prices are rounded to valid TSE tick sizes (buy down, sell up) so the
# figure can be entered as-is. The table below is the standard non-TOPIX100
# grid; TOPIX100 names trade on finer ticks, but every multiple of a coarser
# tick is valid on a finer grid, so rounding here is always placeable.

LIMIT_BAND_SIGMAS = 1.0

TSE_TICK_TABLE = [
    (3_000, 1),
    (5_000, 5),
    (30_000, 10),
    (50_000, 50),
    (300_000, 100),
    (500_000, 500),
    (3_000_000, 1_000),
]

# --------------------------------------------------------------------------
# Verdicts
# --------------------------------------------------------------------------
# score = health (0-4) + valuation (0-4) + trend (0-2)

VERDICT_BANDS = [
    (3, "SELL"),      # 0-3
    (7, "KEEP"),      # 4-7
    (10, "BUY"),      # 8-10
]

# TRIM overrides KEEP: the thing is sound but the price is extreme.
# For an equity, soundness is the health score; for a fund, the structural
# score. Either way it must be at or above this floor before a price-only
# signal is allowed to suggest reducing.
TRIM_SOUNDNESS_FLOOR = 3
TRIM_MIN_ANCHORS_EXPENSIVE = 4
TRIM_PERCENTILE = 85

# For a fund there are no five anchors to count, so a single underlying
# valuation score of 0 — the dearest band — is what stands in for them.
TRIM_ETF_VALUATION_SCORE = 0

# A name reporting within this many days is not scored. Reviewing it on
# figures about to be superseded produces noise dressed as a verdict.
DEFER_DAYS_BEFORE_EARNINGS = 5

# --------------------------------------------------------------------------
# Portfolio
# --------------------------------------------------------------------------
# Holdings are known; weights are not. Concentration is therefore evidenced by
# realised correlation, which needs no position sizes.

CLUSTER_CORRELATION_THRESHOLD = 0.70
CLUSTER_MIN_MEMBERS = 3

# --------------------------------------------------------------------------
# Macro lenses
# --------------------------------------------------------------------------
# Same five lenses, same -2..+2 scale, every run. Movement is the signal, so
# the set is fixed: adding a lens mid-life makes the history incomparable.

MACRO_LENSES = ("ai_bubble", "usdjpy", "us_recession", "japan_domestic", "geopolitics")

# ^TPX returns nothing from this feed, so TOPIX is proxied by 1306.T, the
# largest TOPIX ETF. The tracking error is irrelevant at 3-month horizon.
MACRO_TICKERS = {
    "usdjpy": "JPY=X",
    "topix": "1306.T",
    "nikkei": "^N225",
    "sox": "^SOX",
    "sp500": "^GSPC",
    "vix": "^VIX",
    "gold": "GC=F",
    "us10y": "^TNX",
    "us13w": "^IRX",
    "wti": "CL=F",
}

MACRO_LOOKBACK_SESSIONS = 63       # ~3 months

# Lens thresholds. JUDGMENTS, not facts — edit freely, and expect the Market
# Score to move when you do. Each lens reads -2 (headwind) to +2 (tailwind)
# for a Japan-equity portfolio with unhedged USD assets, and the rules are
# fixed here so the same month always scores the same way.
MACRO_THRESHOLDS = {
    "sox_rollover_pct": -10.0,     # semis falling this much = complex rolling over
    "sox_froth_pct": 25.0,         # semis up this much in 3m = froth risk
    "yen_calm_band_pct": 3.0,      # |3m move| inside this = stable
    "yen_sharp_pct": 8.0,          # beyond this = disorderly either way
    "vix_calm": 20.0,
    "vix_stress": 30.0,
    "curve_deep_inversion": -0.50, # 10y minus 13w, percentage points
    "equity_trend_pct": 5.0,       # TOPIX 3m move that counts as a trend
    "oil_spike_pct": 15.0,         # supply-shock signature
    "gold_spike_pct": 10.0,        # only with oil confirms geopolitics
}

# 0-10 from the five lenses: 5 + (sum of lenses) / 2, clamped and rounded.
MARKET_SCORE_LABELS = [
    (2, "DEFENSIVE"),
    (4, "CAUTIOUS"),
    (6, "NEUTRAL"),
    (8, "CONSTRUCTIVE"),
    (10, "RISK-ON"),
]

# --------------------------------------------------------------------------
# Scorecard
# --------------------------------------------------------------------------

SCORECARD_HORIZONS_MONTHS = (3, 6, 12)
SCORECARD_BENCHMARK = "^TPX"

# Below this many graded verdicts the scorecard reports "insufficient history"
# instead of a hit rate. A rate over one quarter is indistinguishable from
# chance, and printing it invites believing it.
SCORECARD_MIN_VERDICTS = 24


# --------------------------------------------------------------------------
# ETFs — a separate rubric
# --------------------------------------------------------------------------
# An ETF has no earnings, no book value and no business to be healthy, so the
# equity ladder does not apply to it at all. What can go wrong with a fund is
# structural: it gets too small to stay open, too thinly traded to exit
# cheaply, or it drifts from the thing it claims to track. That replaces
# "health" and carries the same 0-4 weight, so both tables end on one 0-10
# score and one verdict.

# Structural scoring, 0-4.
ETF_MIN_AUM_JPY = 10_000_000_000          # below this, size is a real risk
ETF_GOOD_AUM_JPY = 100_000_000_000        # comfortably liquid
ETF_TIGHT_SPREAD_PCT = 0.10               # tight enough to ignore
ETF_MAX_SPREAD_PCT = 0.20                 # beyond this, exit costs bite

# Premium and discount to NAV is REPORTED BUT NOT SCORED. The feed does not
# timestamp navPrice, so most of what looks like a dislocation is a stale NAV
# compared against a live price. Scoring it docked every fund in the universe
# a point for a measurement artefact on the first live run. Only a gap too
# large to be staleness is worth surfacing at all.
ETF_NOTABLE_PREMIUM_PCT = 3.0

# Underlying index valuation. There is no history for an index P/E in the
# feed, so unlike an equity this cannot be a percentile against its own past.
# Instead each fund carries a declared long-run reference multiple, and the
# current figure is scored against that. These are JUDGEMENTS, not facts —
# edit them freely, and expect the score to move when you do.
ETF_REFERENCE_PE = {
    "1655": 18.0,   # S&P 500, long-run forward multiple
    "2559": 17.0,   # MSCI ACWI
    "1658": 13.0,   # MSCI Emerging Markets, structurally cheaper
    "1478": 13.0,   # MSCI Japan High Dividend
    "315A": 11.0,   # Japan banks, structurally low multiple
}

# Scoring bands: current P/E as a ratio of its reference.
ETF_VALUATION_BANDS = [
    (0.80, 4),      # 20%+ below its long-run multiple
    (0.95, 3),
    (1.10, 2),
    (1.30, 1),
    (99.0, 0),      # 30%+ above
]

# A world or country index outside this range is a data error, not a finding.
# 2559 reported a trailing P/E of 3.02 on the first live run.
ETF_PLAUSIBLE_PE_RANGE = (5.0, 60.0)

# Funds with no equity multiple at all — a commodity trust has no P/E, and
# that is a property of the asset, not missing data.
ETF_NO_EARNINGS = {"1540"}   # physical gold
