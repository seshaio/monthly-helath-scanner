"""
Macro lens, portfolio, delta and scorecard tests. Offline.

The macro failure mode is narrative drift: prose that says one thing while
the number says another. Here the basis string is generated from the rule
that fired, and these tests hold that contract — plus the scoring rules
themselves, so a threshold edit that flips a lens shows up as a test change,
not a surprise in next month's report.
"""

import unittest

import numpy as np
import pandas as pd

import config
from monitor import deltas, macro, portfolio, score


def dash(**kv):
    out = {}
    for key, val in kv.items():
        level, chg = val if isinstance(val, tuple) else (val, 0.0)
        out[key] = {"level": level, "chg_3m_pct": chg}
    return out


T = config.MACRO_THRESHOLDS


class Lenses(unittest.TestCase):

    def test_sox_rollover_against_firm_market_is_the_worst_reading(self):
        s, basis = macro.lens_ai_bubble(dash(sox=(100, -12.0), sp500=(100, 3.0)), T)
        self.assertEqual(s, -2)
        self.assertIn("rolling over", basis)

    def test_sox_froth_also_scores_negative(self):
        s, _ = macro.lens_ai_bubble(dash(sox=(100, 30.0), sp500=(100, 10.0)), T)
        self.assertEqual(s, -1)

    def test_sharp_yen_strength_is_the_direct_hit(self):
        s, basis = macro.lens_usdjpy(dash(usdjpy=(140, -9.0)), T)
        self.assertEqual(s, -2)
        self.assertIn("unhedged", basis)

    def test_stable_yen_is_a_mild_positive(self):
        s, _ = macro.lens_usdjpy(dash(usdjpy=(159, 0.5)), T)
        self.assertEqual(s, 1)

    def test_deep_inversion_reads_recessionary(self):
        s, _ = macro.lens_us_recession(dash(us10y=3.5, us13w=4.2, vix=18.0), T)
        self.assertEqual(s, -2)

    def test_oil_and_gold_together_is_the_supply_shock(self):
        s, _ = macro.lens_geopolitics(dash(wti=(100, 20.0), gold=(3000, 12.0)), T)
        self.assertEqual(s, -2)

    def test_gold_alone_reads_monetary_not_war(self):
        s, basis = macro.lens_geopolitics(dash(wti=(100, -2.0), gold=(3000, 12.0)), T)
        self.assertEqual(s, 0)
        self.assertIn("monetary", basis)

    def test_missing_input_is_none_never_zero(self):
        s, _ = macro.lens_ai_bubble(dash(sp500=(100, 3.0)), T)
        self.assertIsNone(s)


class MarketScore(unittest.TestCase):

    def _lenses(self, *scores):
        return {i: {"name": str(i), "score": v, "basis": ""}
                for i, v in enumerate(scores)}

    def test_all_neutral_is_five(self):
        value, _ = macro.market_score(self._lenses(0, 0, 0, 0, 0))
        self.assertEqual(value, 5)

    def test_extremes_clamp_to_the_scale(self):
        self.assertEqual(macro.market_score(self._lenses(-2, -2, -2, -2, -2))[0], 0)
        self.assertEqual(macro.market_score(self._lenses(2, 2, 2, 2, 2))[0], 10)

    def test_one_failed_lens_fails_the_score(self):
        value, _ = macro.market_score(self._lenses(0, 0, None, 0, 0))
        self.assertIsNone(value)


class Clusters(unittest.TestCase):

    def _rows(self, seed=7):
        rng = np.random.default_rng(seed)
        idx = pd.bdate_range("2024-01-01", periods=300, tz="Asia/Tokyo")
        base = rng.normal(0, 0.01, 300)
        def series(common_part, weight):
            noise = rng.normal(0, 0.01, 300)
            return pd.Series(100 * np.exp(np.cumsum(
                weight * common_part + (1 - weight) * noise)), index=idx)
        return [
            {"code": "A1", "_close": series(base, 0.9)},
            {"code": "A2", "_close": series(base, 0.9)},
            {"code": "A3", "_close": series(base, 0.9)},
            {"code": "B1", "_close": series(rng.normal(0, 0.01, 300), 1.0)},
        ]

    def test_comoving_names_form_a_cluster_and_loners_stay_out(self):
        out = portfolio.build(self._rows())
        self.assertEqual(len(out["clusters"]), 1)
        self.assertEqual(out["clusters"][0]["members"], ["A1", "A2", "A3"])

    def test_suspect_series_is_excluded_from_the_matrix(self):
        rows = self._rows()
        rows[0]["data_suspect"] = True
        out = portfolio.build(rows)
        for cluster in out["clusters"]:
            self.assertNotIn("A1", cluster["members"])


class Deltas(unittest.TestCase):

    def test_verdict_change_names_its_component(self):
        prev = {"2502": {"verdict": "KEEP", "score": 5, "health_status": "WATCH",
                         "valuation_score": 1, "trend_score": 1}}
        now = {"2502": {"verdict": "SELL", "score": 3, "health_status": "IMPAIRED",
                        "valuation_score": 1, "trend_score": 1}}
        out = deltas.compare(now, prev)["2502"]
        self.assertTrue(out["verdict_changed"])
        moved = [c["component"] for c in out["causes"]]
        self.assertEqual(moved, ["health_status"])

    def test_new_name_is_marked_new_not_changed(self):
        out = deltas.compare({"9999": {"verdict": "KEEP"}}, {})
        self.assertTrue(out["9999"]["new"])

    def test_no_change_is_silent(self):
        rec = {"verdict": "KEEP", "score": 6, "health_status": "INTACT",
               "valuation_score": 2, "trend_score": 2}
        out = deltas.compare({"8001": dict(rec)}, {"8001": dict(rec)})["8001"]
        self.assertFalse(out["verdict_changed"])
        self.assertEqual(out["causes"], [])


class Scorecard(unittest.TestCase):

    def test_thin_history_reports_insufficient_not_a_rate(self):
        out = score.summarise({3: [{"hit": True}] * 5})
        self.assertFalse(out[3]["sufficient"])
        self.assertNotIn("hit_rate", out[3])

    def test_enough_calls_produce_a_rate(self):
        graded = [{"hit": i % 2 == 0, "excess_pct": float(i - 12)}
                  for i in range(config.SCORECARD_MIN_VERDICTS)]
        out = score.summarise({3: graded})
        self.assertTrue(out[3]["sufficient"])
        self.assertAlmostEqual(out[3]["hit_rate"], 0.5)


if __name__ == "__main__":
    unittest.main(verbosity=2)
