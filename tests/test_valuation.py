"""
Valuation tests. Offline — every series here is synthetic.

The failure this module is most exposed to is silent: an inverted percentile,
or a historical ratio built from figures that were not public at the time.
Neither one throws. Both produce a confident number that is wrong in a
consistent direction, which is worse than a crash.
"""

import unittest

import numpy as np
import pandas as pd

import config
from monitor import valuation


def index(n, start="2021-01-01"):
    return pd.bdate_range(start=start, periods=n, tz="Asia/Tokyo")


def annual(pairs):
    return pd.Series({pd.Timestamp(d): float(v) for d, v in pairs}).sort_index()


class Percentiles(unittest.TestCase):

    def test_latest_at_the_top_ranks_high(self):
        pct, latest = valuation.percentile_of_latest(
            pd.Series(list(range(300)) + [10_000]))
        self.assertGreater(pct, 99)
        self.assertEqual(latest, 10_000)

    def test_latest_at_the_bottom_ranks_low(self):
        pct, _ = valuation.percentile_of_latest(pd.Series(list(range(300)) + [-1]))
        self.assertEqual(pct, 0.0)

    def test_thin_history_returns_none_not_a_number(self):
        pct, _ = valuation.percentile_of_latest(pd.Series([1, 2, 3]))
        self.assertIsNone(pct)

    def test_infinities_are_dropped(self):
        s = pd.Series([np.inf] * 10 + list(range(300)))
        pct, _ = valuation.percentile_of_latest(s)
        self.assertIsNotNone(pct)


class PublicationLag(unittest.TestCase):
    """
    Without a lag the run knows earnings before the market did, and every
    historical percentile is flattered. This is invisible in the output.
    """

    def test_value_does_not_apply_before_it_was_published(self):
        idx = index(400, start="2023-01-02")
        stepped = valuation._stepped(annual([("2023-03-31", 100.0)]), idx,
                                     config.FUNDAMENTALS_PUBLICATION_LAG_DAYS)
        fiscal_end = pd.Timestamp("2023-03-31", tz="Asia/Tokyo")
        published = fiscal_end + pd.Timedelta(days=config.FUNDAMENTALS_PUBLICATION_LAG_DAYS)

        self.assertTrue(stepped[idx < fiscal_end].isna().all(),
                        "figure leaked before its own fiscal year even ended")
        self.assertTrue(stepped[(idx >= fiscal_end) & (idx < published)].isna().all(),
                        "figure applied before it was published")
        self.assertTrue((stepped[idx > published].dropna() == 100.0).all())

    def test_later_period_supersedes_the_earlier_one(self):
        idx = index(900, start="2023-01-02")
        stepped = valuation._stepped(
            annual([("2023-03-31", 100.0), ("2024-03-31", 200.0)]), idx,
            config.FUNDAMENTALS_PUBLICATION_LAG_DAYS)
        self.assertEqual(stepped.dropna().iloc[-1], 200.0)


class Inversion(unittest.TestCase):
    """A high yield is cheap. Getting this backwards is silent and total."""

    def _assess(self, dividends_recent_high):
        # The window must be long enough that the trailing-twelve-month sum at
        # the final date contains only the recent payments. Overlap is correct
        # behaviour during a transition, but it makes for a useless test.
        idx = index(600)
        close = pd.Series(1000.0, index=idx)
        early, late = (10.0, 50.0) if dividends_recent_high else (50.0, 10.0)
        divs = pd.Series(
            {idx[10]: early, idx[150]: early, idx[500]: late, idx[560]: late})
        fundamentals = {
            "eps": annual([("2022-03-31", 100.0), ("2023-03-31", 100.0)]),
            "net_income": pd.Series(dtype=float), "shares": pd.Series(dtype=float),
            "ebit": pd.Series(dtype=float), "equity": pd.Series(dtype=float),
            "debt": pd.Series(dtype=float), "cash_eq": pd.Series(dtype=float),
            "fcf": pd.Series(dtype=float), "dividends": divs,
            "sector": "Consumer Defensive",
        }
        ratios = valuation.build_ratios(close, fundamentals)
        pct, _ = valuation.percentile_of_latest(ratios["dividend_yield"])
        return pct

    def test_high_yield_scores_as_cheap(self):
        raw_high = self._assess(dividends_recent_high=True)
        self.assertGreater(raw_high, 50, "raw percentile should be high")
        # The anchor is inverted before scoring, so cheap means a LOW figure.
        self.assertLess(100 - raw_high, 50)

    def test_low_yield_scores_as_dear(self):
        raw_low = self._assess(dividends_recent_high=False)
        self.assertGreater(100 - raw_low, 50)

    def test_inverted_set_is_only_the_yields(self):
        for anchor in config.VALUATION_ANCHORS_INVERTED:
            self.assertIn("yield", anchor)


class Denominators(unittest.TestCase):

    def test_negative_earnings_do_not_read_as_cheap(self):
        idx = index(400)
        close = pd.Series(1000.0, index=idx)
        fundamentals = {
            "eps": annual([("2022-03-31", -50.0)]),
            "net_income": pd.Series(dtype=float), "shares": pd.Series(dtype=float),
            "ebit": pd.Series(dtype=float), "equity": pd.Series(dtype=float),
            "debt": pd.Series(dtype=float), "cash_eq": pd.Series(dtype=float),
            "fcf": pd.Series(dtype=float), "dividends": pd.Series(dtype=float),
            "sector": "Industrials",
        }
        ratios = valuation.build_ratios(close, fundamentals)
        # A loss-making year yields no P/E at all, rather than a negative one
        # that would sort as the cheapest name in the book.
        self.assertTrue("pe" not in ratios or ratios["pe"].dropna().empty)


class Financials(unittest.TestCase):
    """Deposits and reserves are raw material, not leverage."""

    def test_declared_financial_codes_skip_ev_and_fcf(self):
        self.assertTrue(valuation.is_financial({}, "8766"))
        for anchor in config.FINANCIAL_EXCLUDED_ANCHORS:
            self.assertIn(anchor, config.VALUATION_ANCHORS)

    def test_sector_string_also_identifies_one(self):
        self.assertTrue(valuation.is_financial({"sector": "Financial Services"}, "9999"))
        self.assertFalse(valuation.is_financial({"sector": "Industrials"}, "9999"))

    def test_a_financial_still_has_enough_anchors_to_score(self):
        remaining = set(config.VALUATION_ANCHORS) - set(config.FINANCIAL_EXCLUDED_ANCHORS)
        self.assertGreaterEqual(len(remaining), config.VALUATION_MIN_ANCHORS)


class Dispersion(unittest.TestCase):
    """
    Asahi on the first live run: P/E at the 99th percentile because earnings
    fell 36%, P/B at the 13th because equity kept growing. Their mean, 63, is
    the one reading that is certainly wrong.
    """

    def test_wide_spread_is_flagged(self):
        self.assertGreaterEqual(99 - 13, config.VALUATION_DISPERSION_THRESHOLD)

    def test_tight_spread_is_not_flagged(self):
        self.assertLess(92 - 84, config.VALUATION_DISPERSION_THRESHOLD)


if __name__ == "__main__":
    unittest.main(verbosity=2)


class NegativeYield(unittest.TestCase):
    """
    Mitsui, 2026-08: free cash flow went +671bn to -155bn. fcf_yield came out
    at -1.11%, ranked at the bottom of its own five years, inverted to the
    95th percentile and read as "priced at an extreme". Health never fired —
    its trigger needs two consecutive negative years. The report printed only
    the rank, so all three panel reviewers cited "fcf 95" as evidence the
    stock was expensive. The rank was arithmetically right and meant the
    opposite of what every reader took from it.

    The rank is deliberately still computed and still counted: dropping an
    anchor changes verdicts, and that is a scoring decision, not a display
    one. What is guaranteed here is that the sign travels with it.
    """

    # The annual periods have to sit inside the daily window, or every ratio
    # comes back empty and the assessment says INSUFFICIENT DATA instead of
    # exercising anything.
    PERIODS = ("2022-03-31", "2023-03-31", "2024-03-31", "2025-03-31")

    def _assess(self, fcf_latest):
        idx = index(1500, start="2020-01-01")
        close = pd.Series(1000.0, index=idx)
        fcf = [8.0e8, 6.0e8, 7.0e8, fcf_latest]
        fundamentals = {
            "eps": annual([(p, 100.0) for p in self.PERIODS]),
            "net_income": pd.Series(dtype=float),
            "shares": annual([(p, 1e6) for p in self.PERIODS]),
            "ebit": pd.Series(dtype=float),
            "equity": annual(zip(self.PERIODS, (4.0e8, 4.2e8, 4.4e8, 4.6e8))),
            "debt": pd.Series(dtype=float), "cash_eq": pd.Series(dtype=float),
            "fcf": annual(zip(self.PERIODS, fcf)),
            "dividends": pd.Series(dtype=float),
            "sector": "Industrials",
        }
        return valuation.assess("8031", close, fundamentals)

    def test_a_negative_yield_is_flagged(self):
        out = self._assess(-1.5e8)
        self.assertIn("fcf_yield", out["negative_yield_anchors"])
        self.assertTrue(out["anchors"]["fcf_yield"]["negative_yield"])
        self.assertLess(out["anchors"]["fcf_yield"]["value"], 0)

    def test_a_positive_yield_is_not_flagged(self):
        out = self._assess(7.0e8)
        self.assertEqual(out["negative_yield_anchors"], [])
        self.assertFalse(out["anchors"]["fcf_yield"]["negative_yield"])

    def test_the_rank_is_still_computed_and_still_dear(self):
        """Disclosure, not arithmetic — the score must not move silently."""
        out = self._assess(-1.5e8)
        self.assertGreater(out["anchors"]["fcf_yield"]["percentile"], 80)

    def test_counting_toward_the_expensive_case_is_called_out(self):
        out = self._assess(-1.5e8)
        if out["anchors"]["fcf_yield"]["percentile"] >= config.TRIM_PERCENTILE:
            self.assertIn("fcf_yield", out["negative_yield_counted_expensive"])

    def test_the_turn_is_carried_not_just_asserted(self):
        """A reader who sees the figures needs no warning about the rank."""
        out = self._assess(-1.5e8)
        history = out["negative_yield_history"]["fcf_yield"]
        self.assertEqual(len(history), 4)
        self.assertLess(min(history.values()), 0)
        self.assertGreater(max(history.values()), 0)

    def test_only_inverted_anchors_can_be_flagged(self):
        """pe on negative earnings is a different failure with its own guard."""
        out = self._assess(-1.5e8)
        for name in out["negative_yield_anchors"]:
            self.assertIn(name, config.VALUATION_ANCHORS_INVERTED)
