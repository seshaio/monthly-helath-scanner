"""
Panel and tripwire tests. Offline.

The panel's failure mode is comparability: a reviewer that skipped a name or
free-formed a verdict word silently poisons the matrix. The tripwire's is
noise — an alarm that fires weekly gets unplugged.
"""

import json
import os
import tempfile
import time
import unittest

import pandas as pd

import config

import common
from monitor import consensus, ingest, tripwire


CODES = {"8001", "2502"}


class Ingest(unittest.TestCase):

    def _ok(self, code="8001", verdict="KEEP", **extra):
        entry = {"code": code, "verdict": verdict, "confidence": "high",
                 "rationale": "fine", "price_check": "match"}
        entry.update(extra)
        return entry

    def test_omitted_price_check_is_rejected(self):
        """An unanswered price question is a skipped question, not a shrug."""
        bad = self._ok("8001")
        del bad["price_check"]
        with self.assertRaises(ValueError) as ctx:
            ingest.validate([bad, self._ok("2502")], CODES)
        self.assertIn("price_check", str(ctx.exception))

    def test_unchecked_price_is_allowed(self):
        reviews = ingest.validate(
            [self._ok("8001", price_check="unchecked"), self._ok("2502")], CODES)
        self.assertEqual(reviews["8001"]["price_check"], "unchecked")

    def test_differs_without_a_number_is_rejected(self):
        """Contradicting the price without naming one is not a check."""
        with self.assertRaises(ValueError) as ctx:
            ingest.validate([self._ok("8001", price_check="differs"),
                             self._ok("2502")], CODES)
        self.assertIn("price_observed", str(ctx.exception))

    def test_differs_with_a_number_passes(self):
        reviews = ingest.validate(
            [self._ok("8001", price_check="differs", price_observed=2080.0),
             self._ok("2502")], CODES)
        self.assertEqual(reviews["8001"]["price_observed"], 2080.0)

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


class PriceConfirmation(unittest.TestCase):
    """
    The panel's second job: confirm the price before arguing about it.

    A stale close under a fresher date once shipped unnoticed, so a disputed
    price outranks a disputed verdict — it invalidates the numbers rather
    than contesting their reading.
    """

    def _panel(self):
        return {
            "alpha": {"8001": {"verdict": "KEEP", "rationale": "Friday's close",
                               "price_check": "differs", "price_observed": 2080.0}},
            "beta": {"8001": {"verdict": "KEEP", "rationale": "fine",
                              "price_check": "match"}},
            "gamma": {"8001": {"verdict": "KEEP", "rationale": "no tools",
                               "price_check": "unchecked"}},
            "mechanical": {"8001": {"verdict": "KEEP",
                                    "rationale": "threshold output"}},
        }

    def test_a_dispute_is_surfaced_with_the_claimed_price(self):
        disputes = consensus.price_disputes(self._panel())
        self.assertEqual([c["model"] for c in disputes["8001"]], ["alpha"])
        self.assertEqual(disputes["8001"][0]["observed"], 2080.0)

    def test_mechanical_column_never_votes_on_price(self):
        """It has no way to check a price; a stray field must not read as one."""
        panel = {"mechanical": {"8001": {"verdict": "KEEP",
                                         "rationale": "threshold output",
                                         "price_check": "differs",
                                         "price_observed": 1.0}}}
        self.assertEqual(consensus.price_disputes(panel), {})
        self.assertEqual(consensus.unchecked_prices(panel), {})

    def test_unchecked_is_counted_not_treated_as_confirmation(self):
        self.assertEqual(consensus.unchecked_prices(self._panel()),
                         {"8001": ["gamma"]})

    def test_dispute_leads_the_write_up(self):
        text = consensus.render(
            consensus.matrix(self._panel()), ["alpha", "beta", "gamma"],
            disputes=consensus.price_disputes(self._panel()),
            unchecked=consensus.unchecked_prices(self._panel()))
        self.assertIn("Disputed prices", text)
        self.assertLess(text.index("Disputed prices"),
                        text.index("Agreements"))


class WriteUpLocation(unittest.TestCase):
    """
    The write-up is filed by run name in one folder, so a year of panels can
    be read side by side instead of hunted for across run directories.
    """

    def test_filed_under_output_consensus_by_run_name(self):
        path = consensus.write_up_path("output/2026-08-25-run-5")
        self.assertEqual(os.path.basename(path), "2026-08-25-run-5.md")
        self.assertEqual(os.path.basename(os.path.dirname(path)), "consensus")

    def test_a_symlink_resolves_to_the_real_run(self):
        """`latest` must never file itself as latest.md and overwrite a month."""
        link = os.path.join(config.OUTPUT_DIR, "latest")
        if not os.path.islink(link):
            self.skipTest("no latest symlink in this checkout")
        self.assertNotEqual(os.path.basename(consensus.write_up_path(link)),
                            "latest.md")


class StaleReply(unittest.TestCase):
    """
    The drop folder is reused every month and nothing inside a reply ties it
    to a run. Last month's file has the right tickers, the right shape and
    the right words, so it passes every other check and lands in the new run
    looking like a fresh opinion — the stale-price failure wearing a panel's
    clothes.
    """

    def _run_dir(self, tmp, pack_text="# pack"):
        run = os.path.join(tmp, "2026-08-25-run-9")
        os.makedirs(run)
        with open(os.path.join(run, "data_pack.md"), "w") as fh:
            fh.write(pack_text)
        return run

    def test_a_reply_older_than_the_pack_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            reply = os.path.join(tmp, "gpt.json")
            with open(reply, "w") as fh:
                fh.write("[]")
            time.sleep(0.01)
            run = self._run_dir(tmp)
            with self.assertRaises(ValueError) as ctx:
                ingest.check_answers_this_pack(reply, run)
            self.assertIn("predates", str(ctx.exception))

    def test_a_reply_written_after_the_pack_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = self._run_dir(tmp)
            time.sleep(0.01)
            reply = os.path.join(tmp, "gpt.json")
            with open(reply, "w") as fh:
                fh.write("[]")
            ingest.check_answers_this_pack(reply, run)   # must not raise

    def test_a_run_with_no_pack_is_not_second_guessed(self):
        """No reference point is a reason to stay quiet, not to invent one."""
        with tempfile.TemporaryDirectory() as tmp:
            run = os.path.join(tmp, "2026-08-25-run-9")
            os.makedirs(run)
            reply = os.path.join(tmp, "gpt.json")
            with open(reply, "w") as fh:
                fh.write("[]")
            self.assertIsNone(ingest.pack_written_at(run))
            ingest.check_answers_this_pack(reply, run)   # must not raise

    def test_run_meta_stands_in_when_the_pack_is_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = os.path.join(tmp, "2026-08-25-run-9")
            os.makedirs(run)
            with open(os.path.join(run, "run_meta.json"), "w") as fh:
                json.dump({"generated_at": "2026-08-24T17:12:15+00:00"}, fh)
            self.assertIsNotNone(ingest.pack_written_at(run))
