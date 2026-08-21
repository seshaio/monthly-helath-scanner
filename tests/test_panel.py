"""
Panel and tripwire tests. Offline.

The panel's failure mode is comparability: a reviewer that skipped a name or
free-formed a verdict word silently poisons the matrix. The tripwire's is
noise — an alarm that fires weekly gets unplugged.
"""

import unittest

import pandas as pd

import common
from monitor import consensus, ingest, tripwire


CODES = {"8001", "2502"}


class Ingest(unittest.TestCase):

    def _ok(self, code="8001", verdict="KEEP"):
        return {"code": code, "verdict": verdict, "confidence": "high",
                "rationale": "fine"}

    def test_valid_reply_passes(self):
        reviews = ingest.validate([self._ok("8001"), self._ok("2502", "SELL")], CODES)
        self.assertEqual(set(reviews), CODES)

    def test_unknown_ticker_is_rejected(self):
        with self.assertRaises(ValueError) as ctx:
            ingest.validate([self._ok("9999"), self._ok("8001"),
                             self._ok("2502")], CODES)
        self.assertIn("9999", str(ctx.exception))

    def test_freeform_verdict_is_rejected(self):
        bad = self._ok("8001")
        bad["verdict"] = "STRONG BUY"
        with self.assertRaises(ValueError):
            ingest.validate([bad, self._ok("2502")], CODES)

    def test_missing_name_fails_the_whole_reply(self):
        with self.assertRaises(ValueError) as ctx:
            ingest.validate([self._ok("8001")], CODES)
        self.assertIn("missing", str(ctx.exception))

    def test_every_problem_is_reported_not_just_the_first(self):
        bad1 = self._ok("8001"); bad1["verdict"] = "HODL"
        bad2 = self._ok("2502"); bad2["rationale"] = ""
        message = ""
        try:
            ingest.validate([bad1, bad2], CODES)
        except ValueError as exc:
            message = str(exc)
        self.assertIn("HODL", message)
        self.assertIn("rationale", message)


class Consensus(unittest.TestCase):

    def test_split_is_flagged_and_never_averaged(self):
        panel = {
            "claude": {"2502": {"verdict": "SELL", "rationale": "margins"}},
            "gpt": {"2502": {"verdict": "KEEP", "rationale": "cyclical"}},
            "mechanical": {"2502": {"verdict": "SELL", "rationale": "threshold"}},
        }
        out = consensus.matrix(panel)["2502"]
        self.assertFalse(out["unanimous"])
        self.assertEqual(out["spread"], ["KEEP", "SELL"])
        # The lone dissenter is quoted by name — that is the signal.
        self.assertEqual(out["dissents"][0]["model"], "gpt")

    def test_unanimity_is_quiet(self):
        panel = {m: {"8001": {"verdict": "KEEP", "rationale": ""}}
                 for m in ("a", "b", "mechanical")}
        out = consensus.matrix(panel)["8001"]
        self.assertTrue(out["unanimous"])
        self.assertEqual(out["dissents"], [])


class Tripwire(unittest.TestCase):

    def _frame(self, prices):
        idx = pd.bdate_range("2026-02-02", periods=len(prices), tz="Asia/Tokyo")
        return pd.DataFrame({"8001.T": prices}, index=idx)

    def _saved(self, buy=1900.0, sell=2200.0):
        return [{"code": "8001", "buy_limit_1m": buy, "sell_limit_1m": sell}]

    def test_quiet_inside_the_band(self):
        fired = tripwire.check(self._saved(), self._frame([2000.0] * 120), {})
        self.assertEqual(fired, [])

    def test_band_breach_fires(self):
        prices = [2000.0] * 115 + [1990, 1960, 1930, 1900, 1870]
        fired = tripwire.check(self._saved(), self._frame(prices), {})
        self.assertTrue(any("below the monthly band" in msg for _, msg in fired))

    def test_earnings_inside_window_fires(self):
        fired = tripwire.check(self._saved(), self._frame([2000.0] * 120),
                               {"8001": 3})
        self.assertTrue(any("reports in 3" in msg for _, msg in fired))

    def test_past_earnings_date_never_fires(self):
        fired = tripwire.check(self._saved(), self._frame([2000.0] * 120),
                               {"8001": -9})
        self.assertEqual(fired, [])

    def test_missing_feed_is_an_alert_not_silence(self):
        empty = pd.DataFrame({"9999.T": []})
        fired = tripwire.check(self._saved(), empty, {})
        self.assertTrue(any("check the feed" in msg for _, msg in fired))


if __name__ == "__main__":
    unittest.main(verbosity=2)
