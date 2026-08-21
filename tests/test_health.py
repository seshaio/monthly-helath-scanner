"""
Health ladder tests. Offline.

Two failure modes matter here and neither one throws. A missing field can
read as a clean bill of health, and a trigger that clears its threshold by a
hundredth produces the same verdict as one that clears it by a mile.
"""

import unittest

import pandas as pd

import config
from monitor import health


def annual(pairs):
    return pd.Series({pd.Timestamp(d): float(v) for d, v in pairs}).sort_index()


def fundamentals(**overrides):
    """A sound business by every trigger, unless told otherwise."""
    base = {
        "revenue": annual([("2024-03-31", 1000.0), ("2025-03-31", 1050.0)]),
        "operating_income": annual([("2024-03-31", 100.0), ("2025-03-31", 105.0)]),
        "net_income": annual([("2024-03-31", 80.0), ("2025-03-31", 84.0)]),
        "equity": annual([("2024-03-31", 500.0), ("2025-03-31", 540.0)]),
        "debt": annual([("2024-03-31", 200.0), ("2025-03-31", 200.0)]),
        "cash_eq": annual([("2024-03-31", 100.0), ("2025-03-31", 100.0)]),
        "ebitda": annual([("2024-03-31", 150.0), ("2025-03-31", 150.0)]),
        "fcf": annual([("2024-03-31", 50.0), ("2025-03-31", 55.0)]),
        "eps": pd.Series(dtype=float), "shares": pd.Series(dtype=float),
        "ebit": pd.Series(dtype=float), "dividends": pd.Series(dtype=float),
        "sector": "Industrials",
    }
    base.update(overrides)
    return base


class Ladder(unittest.TestCase):

    def test_sound_business_is_intact(self):
        out = health.assess("9999", fundamentals())
        self.assertEqual(out["status"], config.HEALTH_INTACT)
        self.assertEqual(out["health_score"], 4)

    def test_one_trigger_is_watch(self):
        out = health.assess("9999", fundamentals(
            operating_income=annual([("2024-03-31", 100.0), ("2025-03-31", 60.0)])))
        self.assertEqual(out["status"], config.HEALTH_WATCH)

    def test_two_triggers_are_impaired(self):
        out = health.assess("9999", fundamentals(
            operating_income=annual([("2024-03-31", 100.0), ("2025-03-31", 60.0)]),
            revenue=annual([("2024-03-31", 1000.0), ("2025-03-31", 850.0)])))
        self.assertEqual(out["status"], config.HEALTH_IMPAIRED)

    def test_broken_is_never_inferred_only_declared(self):
        collapsing = fundamentals(
            operating_income=annual([("2024-03-31", 100.0), ("2025-03-31", 1.0)]),
            revenue=annual([("2024-03-31", 1000.0), ("2025-03-31", 500.0)]),
            net_income=annual([("2024-03-31", 80.0), ("2025-03-31", 1.0)]),
            fcf=annual([("2024-03-31", -50.0), ("2025-03-31", -60.0)]))
        self.assertEqual(health.assess("9999", collapsing)["status"],
                         config.HEALTH_IMPAIRED)
        declared = health.assess("9999", collapsing,
                                 [{"type": "going_concern_doubt", "date": "", "note": ""}])
        self.assertEqual(declared["status"], config.HEALTH_BROKEN)

    def test_a_severe_declaration_alone_reaches_impaired(self):
        out = health.assess("9999", fundamentals(),
                            [{"type": "restatement", "date": "", "note": ""}])
        self.assertEqual(out["status"], config.HEALTH_IMPAIRED)


class MissingData(unittest.TestCase):
    """Silence from the feed is not a clean bill of health."""

    def test_no_statements_is_unassessed_not_intact(self):
        empty = {k: pd.Series(dtype=float) for k in
                 ("revenue", "operating_income", "net_income", "equity", "debt",
                  "cash_eq", "ebitda", "fcf", "eps", "shares", "ebit", "dividends")}
        empty["sector"] = "Industrials"
        out = health.assess("9999", empty)
        self.assertIsNone(out["status"])
        self.assertIsNone(out["health_score"])

    def test_healthy_company_is_not_marked_unassessed(self):
        # The bug this replaces: zero fired and zero untested satisfied the
        # old guard, so the cleanest balance sheets scored as "no statements".
        out = health.assess("9999", fundamentals())
        self.assertEqual(out["status"], config.HEALTH_INTACT)

    def test_single_period_cannot_be_judged(self):
        out = health.assess("9999", fundamentals(
            revenue=annual([("2025-03-31", 1000.0)]),
            operating_income=annual([("2025-03-31", 100.0)]),
            net_income=annual([("2025-03-31", 80.0)]),
            equity=annual([("2025-03-31", 500.0)])))
        self.assertIsNone(out["status"])


class Financials(unittest.TestCase):

    def test_leverage_is_not_tested_for_a_financial(self):
        out = health.assess("8766", fundamentals(sector="Financial Services"))
        untested = [u["trigger"] for u in out["unavailable"]]
        self.assertIn("net_debt_to_ebitda_above", untested)

    def test_a_financial_can_still_be_assessed(self):
        out = health.assess("8766", fundamentals(sector="Financial Services"))
        self.assertIsNotNone(out["status"])


class Marginal(unittest.TestCase):
    """
    Asahi fired the leverage trigger at 4.01x against a 4.0x threshold, and
    that hundredth was the difference between KEEP and SELL.
    """

    def test_hairline_trigger_is_flagged(self):
        # Net debt 601 - 0 cash, EBITDA 150 -> 4.007x against a 4.0 threshold.
        out = health.assess("9999", fundamentals(
            debt=annual([("2024-03-31", 601.0), ("2025-03-31", 601.0)]),
            cash_eq=annual([("2024-03-31", 0.0), ("2025-03-31", 0.0)])))
        self.assertEqual(out["status"], config.HEALTH_WATCH)
        self.assertIn("marginal_trigger", out)
        self.assertEqual(out["marginal_trigger"]["would_be"], config.HEALTH_INTACT)

    def test_decisive_trigger_is_not_flagged(self):
        out = health.assess("9999", fundamentals(
            debt=annual([("2024-03-31", 2000.0), ("2025-03-31", 2000.0)]),
            cash_eq=annual([("2024-03-31", 0.0), ("2025-03-31", 0.0)])))
        self.assertNotIn("marginal_trigger", out)

    def test_net_cash_is_floored_not_read_as_distress(self):
        out = health.assess("9999", fundamentals(
            debt=annual([("2024-03-31", 10.0), ("2025-03-31", 10.0)]),
            cash_eq=annual([("2024-03-31", 900.0), ("2025-03-31", 900.0)])))
        self.assertEqual(out["status"], config.HEALTH_INTACT)


if __name__ == "__main__":
    unittest.main(verbosity=2)
