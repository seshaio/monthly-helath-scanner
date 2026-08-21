"""
ETF rubric and verdict tests. Offline.

The ETF failure mode is subtler than the equity one: nothing throws, the
numbers look reasonable, and a fund gets marked SELL because its wrapper is
unremarkable rather than because anything is wrong with it.
"""

import unittest

import config
from monitor import etf
from monitor import verdict


def profile(aum=200e9, bid=1000.0, ask=1000.5, nav=1000.0, pe=18.0):
    return {"aum_jpy": aum, "bid": bid, "ask": ask, "nav": nav, "index_pe": pe}


class Structure(unittest.TestCase):
    """Starts sound and deducts, so 'adequate' does not read as 'failing'."""

    def test_large_and_tight_is_sound(self):
        score, notes = etf.structural_score(profile(), 1000.0)
        self.assertEqual(score, 4)
        self.assertEqual(notes, [])

    def test_adequate_fund_is_not_dragged_to_failure(self):
        # 1658 on the first live run: usable, unremarkable, and scored 1/4 by
        # the first cut of this — which dragged the whole name to SELL.
        score, _ = etf.structural_score(
            profile(aum=29e9, bid=1000.0, ask=1003.2), 1000.0)
        self.assertGreaterEqual(score, 2)

    def test_closure_risk_scores_near_zero(self):
        score, notes = etf.structural_score(profile(aum=2e9), 1000.0)
        self.assertLessEqual(score, 1)
        self.assertTrue(any("closure risk" in n for n in notes))

    def test_premium_is_noted_but_never_scored(self):
        tight = etf.structural_score(profile(nav=1000.0), 1000.0)[0]
        dislocated = etf.structural_score(profile(nav=1000.0), 1080.0)[0]
        self.assertEqual(tight, dislocated, "premium must not move the score")
        _, notes = etf.structural_score(profile(nav=1000.0), 1080.0)
        self.assertTrue(any("NAV" in n for n in notes))

    def test_score_never_goes_negative(self):
        score, _ = etf.structural_score(
            {"aum_jpy": 1e8, "bid": None, "ask": None, "nav": None}, 1000.0)
        self.assertGreaterEqual(score, 0)


class Underlying(unittest.TestCase):

    def test_cheap_index_scores_high(self):
        out = etf.underlying_valuation("1655", profile(pe=12.0))
        self.assertEqual(out["score"], 4)

    def test_dear_index_scores_zero(self):
        out = etf.underlying_valuation("1655", profile(pe=30.0))
        self.assertEqual(out["score"], 0)

    def test_implausible_multiple_is_refused(self):
        # 2559 reported a trailing P/E of 3.02 for a world equity index.
        out = etf.underlying_valuation("2559", profile(pe=3.02))
        self.assertTrue(out["suspect"])
        self.assertIsNone(out["score"])

    def test_commodity_has_no_multiple_by_nature(self):
        out = etf.underlying_valuation("1540", profile(pe=None))
        self.assertIsNone(out["score"])
        self.assertIn("commodity", out["label"])

    def test_reference_is_declared_for_every_scorable_fund(self):
        for code in config.ETF_REFERENCE_PE:
            self.assertNotIn(code, config.ETF_NO_EARNINGS)


class NavVerification(unittest.TestCase):
    """A human-verified stale NAV silences the flag without faking a fix."""

    def test_verified_stale_nav_is_not_flagged(self):
        _, notes = etf.structural_score(profile(nav=1951.87), 1872.5,
                                        nav_verified=True)
        self.assertFalse(any("vs NAV" in n and "verified" not in n for n in notes))
        self.assertTrue(any("verified unreliable" in n for n in notes))

    def test_unverified_gap_still_flags(self):
        _, notes = etf.structural_score(profile(nav=1951.87), 1872.5,
                                        nav_verified=False)
        self.assertTrue(any("worth a look" in n for n in notes))

    def test_verification_does_not_change_the_score(self):
        flagged = etf.structural_score(profile(nav=1951.87), 1872.5, False)[0]
        verified = etf.structural_score(profile(nav=1951.87), 1872.5, True)[0]
        self.assertEqual(flagged, verified)


class Assumptions(unittest.TestCase):
    """A declared thesis moves the score mechanically and is always labelled."""

    ASSUMPTION = {"reference_pe": {"value": 13.0, "date": "2026-08-21",
                                   "note": "BOJ normalization"}}

    def test_override_changes_the_score(self):
        base = etf.underlying_valuation("315A", profile(pe=16.0))
        scenario = etf.underlying_valuation("315A", profile(pe=16.0),
                                            self.ASSUMPTION)
        self.assertEqual(base["score"], 0)        # 16.0 / 11 = +45%
        self.assertEqual(scenario["score"], 1)    # 16.0 / 13 = +23%

    def test_override_is_always_labelled(self):
        out = etf.underlying_valuation("315A", profile(pe=16.0), self.ASSUMPTION)
        self.assertIn("scenario reference", out["label"])
        self.assertIn("2026-08-21", out["label"])

    def test_no_assumption_means_base_rules(self):
        out = etf.underlying_valuation("315A", profile(pe=16.0), None)
        self.assertIsNone(out["assumption"])


class Verdicts(unittest.TestCase):

    def test_sound_and_cheap_buys(self):
        self.assertEqual(verdict.decide(9, soundness=4), verdict.BUY)

    def test_sound_but_dear_trims_rather_than_sells(self):
        self.assertEqual(
            verdict.decide(6, soundness=4,
                           expensive_anchors=config.TRIM_MIN_ANCHORS_EXPENSIVE),
            verdict.TRIM)

    def test_price_alone_never_reaches_sell(self):
        # Soundness scores 4 on its own, which is the KEEP floor, so the
        # dearest possible thing with the worst trend still cannot be sold on
        # valuation. Only deterioration reaches SELL.
        worst = verdict.decide(4 + 0 + 0, soundness=4, expensive_anchors=5)
        self.assertIn(worst, (verdict.KEEP, verdict.TRIM))
        self.assertNotEqual(worst, verdict.SELL)

    def test_broken_sells_however_cheap(self):
        self.assertEqual(verdict.decide(10, soundness=0, broken=True), verdict.SELL)

    def test_imminent_earnings_defers(self):
        self.assertEqual(
            verdict.decide(9, soundness=4,
                           days_to_earnings=config.DEFER_DAYS_BEFORE_EARNINGS - 1),
            verdict.WAIT)

    def test_earnings_well_ahead_does_not_defer(self):
        self.assertEqual(
            verdict.decide(9, soundness=4,
                           days_to_earnings=config.DEFER_DAYS_BEFORE_EARNINGS + 10),
            verdict.BUY)

    def test_missing_component_yields_no_verdict(self):
        self.assertIsNone(verdict.total(4, None, 2))
        self.assertEqual(verdict.decide(None, soundness=4), verdict.INCOMPLETE)

    def test_every_verdict_word_has_an_explanation(self):
        for word in (verdict.BUY, verdict.KEEP, verdict.TRIM, verdict.SELL,
                     verdict.WAIT, verdict.INCOMPLETE):
            self.assertTrue(verdict.explain(word))


class NearBuy(unittest.TestCase):
    """The near-BUY line states distances, never predictions."""

    def _row(self, score=7, health=4, trend=1, vs_ma=-1.2, r12=10.0,
             vscore=2, mean=55.0):
        return {"code": "6383", "asset_type": "Equity", "_score": score,
                "health": {"health_score": health}, "trend_score": trend,
                "vs_ma_200_pct": vs_ma, "return_12m_pct": r12,
                "valuation": {"valuation_score": vscore, "mean_percentile": mean}}

    def test_seven_with_full_health_qualifies(self):
        from monitor import report
        out = report.near_buy([self._row()])
        self.assertEqual(out[0][0], "6383")
        self.assertIn("200d", out[0][1])

    def test_seven_with_slipped_health_is_not_nearly_a_buy(self):
        # 2+3+2 is also 7, but the missing point is the business itself.
        from monitor import report
        out = report.near_buy([self._row(health=2, vscore=3, trend=2)])
        self.assertEqual(out, [])

    def test_eight_and_six_are_ignored(self):
        from monitor import report
        self.assertEqual(report.near_buy([self._row(score=8)]), [])
        self.assertEqual(report.near_buy([self._row(score=6)]), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
