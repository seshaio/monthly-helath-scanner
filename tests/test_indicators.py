"""
Offline tests. No network, no fixtures to refresh, runs in about a second.

Every test here is a real incident that already happened on this project or
its sibling. The guards exist because the failure did, and the one failure
mode that matters most is a broken feed that reads as a finding: a 90% fall
that was a split, a price of zero that was a timeout. None of those are facts
about a company, and none of them may reach a report as if they were.
"""

import unittest
from datetime import datetime

import numpy as np
import pandas as pd

import common
import config
from monitor import indicators


def series(values, start="2020-01-01"):
    """Business-day price series with a tz-aware index, as yfinance returns."""
    idx = pd.bdate_range(start=start, periods=len(values), tz="Asia/Tokyo")
    return pd.Series([float(v) for v in values], index=idx)


class WilderRSI(unittest.TestCase):
    """RSI is computed, never retrieved — so it has to be provably right."""

    # Wilder, New Concepts in Technical Trading Systems (1978), worked example.
    CLOSES = [44.34, 44.09, 44.15, 43.61, 44.33, 44.83, 45.10, 45.42, 45.84,
              46.08, 45.89, 46.03, 45.61, 46.28, 46.28, 46.00, 46.03, 46.41,
              46.22, 45.64]
    PUBLISHED = {14: 70.53, 15: 66.32, 16: 66.55, 17: 69.41, 18: 66.36, 19: 57.97}

    def test_matches_published_table(self):
        for i, expected in self.PUBLISHED.items():
            got = indicators.wilder_rsi(pd.Series(self.CLOSES[:i + 1]))
            # Wilder rounds intermediate averages to 2dp in print, so the
            # published figures sit a consistent ~0.07 above an exact run.
            self.assertAlmostEqual(got, expected, delta=0.1)

    def test_all_gains_reads_100(self):
        self.assertEqual(indicators.wilder_rsi(series(range(1, 40))), 100.0)

    def test_too_short_is_nan_not_zero(self):
        # Zero would be read as "maximally oversold" — a finding invented from
        # a gap in data.
        self.assertTrue(np.isnan(indicators.wilder_rsi(series([1, 2, 3]))))


class PriceBreaks(unittest.TestCase):
    """
    Both incidents from the first live run, 2026-08-21.

    2559 fell 90% on an unrecorded 1:10 split and 1655 printed 33.96 in a
    series running at 342. The feed reported no split for either, so
    auto_adjust did nothing. Unguarded, 2559 read as -86% over 12 months.
    """

    def test_split_is_detected(self):
        # 100 sessions at ~300, then a clean 10x drop that holds.
        prices = [300] * 100 + [30] * 20
        found = indicators.detect_breaks(series(prices))
        self.assertEqual(len(found), 1)
        self.assertIn("split", found[0]["looks_like"])
        self.assertFalse(found[0]["recovered"])

    def test_bad_print_is_not_called_a_split(self):
        # The 1655 case: ratio looks exactly like a 10:1 split, but the series
        # returns to its old level. Classifying by ratio alone got this wrong.
        prices = [342] * 100 + [33.9, 35.7] + [345] * 20
        found = indicators.detect_breaks(series(prices))
        self.assertTrue(found, "a 10x move must always be flagged")
        self.assertIn("bad print", found[0]["looks_like"])
        self.assertTrue(found[0]["recovered"])

    def test_ordinary_volatility_is_not_flagged(self):
        rng = np.random.default_rng(0)
        walk = 1000 * np.exp(np.cumsum(rng.normal(0, 0.02, 400)))
        self.assertEqual(indicators.detect_breaks(series(walk)), [])

    def test_suspect_series_is_never_scored(self):
        prices = [300] * 300 + [30] * 20
        out = indicators.compute(series(prices))
        self.assertTrue(out["data_suspect"])
        self.assertIsNone(indicators.trend_score(out))
        # Nothing derived from a broken history may appear at all.
        for derived in ("rsi_14", "return_12m_pct", "volatility_1y_pct"):
            self.assertNotIn(derived, out)

    def test_last_price_survives_a_break(self):
        # The latest print is observably right even when the history is not.
        out = indicators.compute(series([300] * 300 + [30] * 20))
        self.assertEqual(out["last_price"], 30.0)


class Corrections(unittest.TestCase):
    """Declared corporate actions are applied explicitly and recorded."""

    def test_split_makes_the_series_continuous(self):
        raw = series([3000] * 50 + [300] * 50)
        split_date = raw.index[50].strftime("%Y-%m-%d")
        fixed, applied = indicators.apply_corrections(
            raw, {"splits": [{"date": split_date, "ratio": 10}], "bad_prints": []})
        self.assertEqual(applied[0]["sessions_rescaled"], 50)
        self.assertEqual(indicators.detect_breaks(fixed), [])

    def test_bad_print_session_is_dropped(self):
        raw = series([342] * 50 + [33.9] + [345] * 50)
        bad_date = raw.index[50].strftime("%Y-%m-%d")
        fixed, applied = indicators.apply_corrections(
            raw, {"splits": [], "bad_prints": [{"date": bad_date}]})
        self.assertEqual(len(fixed), len(raw) - 1)
        self.assertEqual(applied[0]["sessions_dropped"], 1)
        self.assertEqual(indicators.detect_breaks(fixed), [])

    def test_no_corrections_leaves_the_series_alone(self):
        raw = series([100] * 30)
        fixed, applied = indicators.apply_corrections(raw, None)
        self.assertEqual(applied, [])
        pd.testing.assert_series_equal(fixed, raw)


class MissingData(unittest.TestCase):
    """A gap in coverage is never a negative finding about an instrument."""

    def test_short_history_is_reported_not_scored(self):
        out = indicators.compute(series([100] * 50))
        self.assertTrue(out["insufficient_history"])
        self.assertIsNone(indicators.trend_score(out))
        self.assertNotIn("rsi_14", out)

    def test_empty_feed_raises_rather_than_returning_zeros(self):
        """An empty frame must stop the run, not read as a set of flat prices."""
        original = indicators.yf.download
        indicators.yf.download = lambda *a, **k: pd.DataFrame()
        try:
            with self.assertRaises(common.DataFeedError):
                indicators.fetch_history([{"code": "7203"}])
        finally:
            indicators.yf.download = original

    def test_mostly_missing_feed_fails_the_run(self):
        """
        Half the universe returning nothing is a feed failure, not a universe
        problem. Scoring the survivors would produce a report that looks
        complete and is not.
        """
        items = [{"code": c, "asset_type": "Equity", "held": True,
                  "fx": None, "note": ""} for c in ("1111", "2222", "3333", "4444")]
        idx = pd.bdate_range("2024-01-01", periods=300, tz="Asia/Tokyo")
        frame = pd.DataFrame({"1111.T": np.linspace(100, 110, 300)}, index=idx)

        original_fetch = indicators.fetch_history
        original_corr = indicators.universe_mod.corrections
        indicators.fetch_history = lambda _items: frame
        indicators.universe_mod.corrections = lambda: {}
        try:
            with self.assertRaises(common.DataFeedError) as ctx:
                indicators.build(items)
            self.assertIn("feed failure", str(ctx.exception))
        finally:
            indicators.fetch_history = original_fetch
            indicators.universe_mod.corrections = original_corr

    def test_nan_serialises_to_null_not_the_NaN_token(self):
        # json.dump emits a bare NaN, which is not valid JSON and which every
        # downstream reader chokes on.
        self.assertIsNone(common._plain(float("nan")))
        self.assertIsNone(common._plain(np.float64("nan")))


class Scoring(unittest.TestCase):
    """Trend is deliberately small — it breaks ties, it does not decide."""

    def test_trend_caps_at_two(self):
        out = indicators.compute(series(np.linspace(100, 200, 400)))
        self.assertEqual(indicators.trend_score(out), 2)
        self.assertLessEqual(indicators.trend_score(out),
                             config.TREND_ABOVE_MA_POINTS
                             + config.TREND_POSITIVE_12M_POINTS)

    def test_falling_series_scores_zero(self):
        out = indicators.compute(series(np.linspace(200, 100, 400)))
        self.assertEqual(indicators.trend_score(out), 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)


class Settlement(unittest.TestCase):
    """
    The incident: a run at 00:55 JST stamped thirteen Friday closes as
    Monday's, because six ETFs had filled and the equities had not. Its
    cousin: a run 26 minutes after the bell read 8001 at 2072.5 against a
    settled 2080.0. Neither is distinguishable from a good close by looking
    at the number, so both are handled by the clock, not by inspection.
    """

    def _frame(self, days, tz="Asia/Tokyo"):
        idx = pd.DatetimeIndex([pd.Timestamp(d, tz=tz) for d in days])
        return pd.DataFrame({"8001.T": [1.0] * len(days)}, index=idx)

    def test_a_bar_from_an_open_session_is_dropped(self):
        """Mid-session on the 25th: that day's bar is a live price, not a close."""
        now = datetime(2026, 8, 25, 10, 0, tzinfo=common.JST)
        self.assertFalse(common.is_settled(datetime(2026, 8, 25).date(), now))

    def test_the_bell_alone_does_not_settle_a_bar(self):
        """15:56 was measurably still moving — the close is not final at 15:30."""
        now = datetime(2026, 8, 25, 15, 56, tzinfo=common.JST)
        self.assertFalse(common.is_settled(datetime(2026, 8, 25).date(), now))

    def test_next_morning_is_settled(self):
        now = datetime(2026, 8, 26, 7, 0, tzinfo=common.JST)
        self.assertTrue(common.is_settled(datetime(2026, 8, 25).date(), now))

    def test_weekend_walks_back_to_friday(self):
        now = datetime(2026, 8, 23, 9, 0, tzinfo=common.JST)   # Sunday
        self.assertEqual(common.last_settled_session(now).isoformat(),
                         "2026-08-21")

    def test_before_the_close_walks_back_to_the_prior_session(self):
        now = datetime(2026, 8, 25, 8, 0, tzinfo=common.JST)   # Tue pre-open
        self.assertEqual(common.last_settled_session(now).isoformat(),
                         "2026-08-24")

    def test_unsettled_tail_is_trimmed_and_history_kept(self):
        frame = self._frame(["2026-08-20", "2026-08-21", "2026-08-24"])
        original = indicators.common.is_settled
        indicators.common.is_settled = lambda d, now=None: d.isoformat() < "2026-08-24"
        try:
            out = indicators.drop_unsettled(frame)
        finally:
            indicators.common.is_settled = original
        self.assertEqual([str(i.date()) for i in out.index],
                         ["2026-08-20", "2026-08-21"])

    def test_settled_frame_is_untouched(self):
        frame = self._frame(["2026-08-20", "2026-08-21"])
        original = indicators.common.is_settled
        indicators.common.is_settled = lambda d, now=None: True
        try:
            self.assertIs(indicators.drop_unsettled(frame), frame)
        finally:
            indicators.common.is_settled = original


class MixedSessions(unittest.TestCase):
    """A report is only as current as its stalest name."""

    ROWS = [{"code": "8001", "as_of": "2026-08-21"},
            {"code": "7532", "as_of": "2026-08-21"},
            {"code": "1655", "as_of": "2026-08-24"}]

    def test_sessions_group_oldest_first(self):
        out = common.price_sessions(self.ROWS)
        self.assertEqual(out, [("2026-08-21", ["7532", "8001"]),
                               ("2026-08-24", ["1655"])])

    def test_a_name_without_a_date_is_not_invented(self):
        out = common.price_sessions(self.ROWS + [{"code": "9999", "as_of": None}])
        self.assertNotIn("9999", [c for _, codes in out for c in codes])

    def test_the_stamp_is_the_oldest_close_not_the_newest(self):
        """The exact inversion that shipped Friday prices under Monday's date."""
        from monitor import report
        text = report.render(
            [dict(r, asset_type="Equity") for r in self.ROWS], "2026-08-21",
            sessions=common.price_sessions(self.ROWS))
        self.assertIn("not all from the same session", text)
        self.assertIn("2026-08-21", text.split("\n")[0])


class CacheCoverage(unittest.TestCase):
    """
    The 07:43 incident: a cache written at 02:03, when the feed had Monday's
    ETF bars and none of its equity bars, was still reused six hours later
    because Monday had "settled" by the clock in both moments. The feed had
    filled in between — 8001 was there at 2,117.5 — and the run reported
    Friday's 2,080.0 again. A cache that was ragged when written must not be
    preserved; only the session it genuinely covers counts.
    """

    def _frame(self, rows):
        idx = pd.DatetimeIndex(
            [pd.Timestamp(d, tz="Asia/Tokyo") for d, _ in rows])
        return pd.DataFrame(
            {"8001.T": [v[0] for _, v in rows],
             "1655.T": [v[1] for _, v in rows]}, index=idx)

    def test_a_full_last_row_covers_that_session(self):
        frame = self._frame([("2026-08-21", (2080.0, 876.0)),
                             ("2026-08-24", (2117.5, 876.2))])
        self.assertEqual(indicators.covered_through(frame), "2026-08-24")

    def test_a_partial_last_row_covers_only_the_session_before(self):
        """Six ETFs filled and thirteen equities not is not Monday's data."""
        frame = self._frame([("2026-08-21", (2080.0, 876.0)),
                             ("2026-08-24", (np.nan, 876.2))])
        self.assertEqual(indicators.covered_through(frame), "2026-08-21")

    def test_nothing_complete_covers_nothing(self):
        frame = self._frame([("2026-08-21", (np.nan, 876.0)),
                             ("2026-08-24", (np.nan, 876.2))])
        self.assertIsNone(indicators.covered_through(frame))

    def test_coverage_below_the_settled_session_forces_a_refetch(self):
        """The exact reuse condition that served a stale price at 07:43."""
        frame = self._frame([("2026-08-21", (2080.0, 876.0)),
                             ("2026-08-24", (np.nan, 876.2))])
        self.assertNotEqual(indicators.covered_through(frame), "2026-08-24")
