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
    "tvdivq0000001vg2-att/data_j.xls"
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
RSI_PERIOD = 14                # Wilder's smoothing, not simple MA
MOVING_AVERAGE_DAYS = 200
VOLATILITY_WINDOW_DAYS = 252
CORRELATION_WINDOW_DAYS = 252

# A price series shorter than this cannot support the indicators, so the name
# is reported as insufficient-history rather than scored on a partial window.
MIN_TRADING_DAYS = 200

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
# Verdicts
# --------------------------------------------------------------------------
# score = health (0-4) + valuation (0-4) + trend (0-2)

VERDICT_BANDS = [
    (3, "SELL"),      # 0-3
    (7, "KEEP"),      # 4-7
    (10, "BUY"),      # 8-10
]

# TRIM overrides KEEP: the business is sound but the price is extreme.
# Health must be INTACT and this many anchors at or above the percentile.
TRIM_MIN_ANCHORS_EXPENSIVE = 4
TRIM_PERCENTILE = 85

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

MACRO_TICKERS = {
    "usdjpy": "JPY=X",
    "topix": "^TPX",
    "nikkei": "^N225",
    "sox": "^SOX",
    "sp500": "^GSPC",
    "vix": "^VIX",
    "gold": "GC=F",
    "us10y": "^TNX",
    "wti": "CL=F",
}

# --------------------------------------------------------------------------
# Scorecard
# --------------------------------------------------------------------------

SCORECARD_HORIZONS_MONTHS = (3, 6, 12)
SCORECARD_BENCHMARK = "^TPX"

# Below this many graded verdicts the scorecard reports "insufficient history"
# instead of a hit rate. A rate over one quarter is indistinguishable from
# chance, and printing it invites believing it.
SCORECARD_MIN_VERDICTS = 24
