"""
Limit-band and tick tests. Offline.

The band exists to be typed into an order form, so the only failure that
matters is a price that is not placeable: off-grid, or on the wrong side of
the level it claims to mark.
"""

import unittest

import numpy as np
import pandas as pd

import config
from monitor import indicators


class Ticks(unittest.TestCase):

    def test_grid_boundaries(self):
        self.assertEqual(indicators.tick_size(2_999), 1)
        self.assertEqual(indicators.tick_size(3_000), 1)
        self.assertEqual(indicators.tick_size(3_001), 5)
        self.assertEqual(indicators.tick_size(5_001), 10)
        self.assertEqual(indicators.tick_size(29_000), 10)
        self.assertEqual(indicators.tick_size(31_000), 50)

    def test_buy_rounds_down_sell_rounds_up(self):
        self.assertEqual(indicators.round_to_tick(4_703.7, up=False), 4_700)
        self.assertEqual(indicators.round_to_tick(4_703.7, up=True), 4_705)

    def test_on_grid_price_is_unchanged(self):
        self.assertEqual(indicators.round_to_tick(4_700.0, up=False), 4_700)
        self.assertEqual(indicators.round_to_tick(4_700.0, up=True), 4_700)

    def test_tick_follows_the_candidate_not_the_last_trade(self):
        # A name trading at 5,100 with a buy band at ~4,703 ticks in ¥5,
        # because the ORDER is below 5,000 — the last trade is irrelevant.
        self.assertEqual(indicators.round_to_tick(4_703.0, up=False) % 5, 0)


class Band(unittest.TestCase):

    def test_band_brackets_the_price(self):
        buy, sell = indicators.limit_band(1_000.0, 24.0)
        self.assertLess(buy, 1_000.0)
        self.assertGreater(sell, 1_000.0)

    def test_higher_volatility_widens_the_band(self):
        calm = indicators.limit_band(10_000.0, 15.0)
        wild = indicators.limit_band(10_000.0, 45.0)
        self.assertLess(wild[0], calm[0])
        self.assertGreater(wild[1], calm[1])

    def test_width_matches_the_math(self):
        price, vol = 10_000.0, 24.0
        buy, sell = indicators.limit_band(price, vol)
        sigma = vol / 100 / np.sqrt(12)
        # Rounding is conservative, so the band is at least the raw sigma.
        self.assertLessEqual(buy, price * (1 - sigma) + 10)
        self.assertGreaterEqual(sell, price * (1 + sigma) - 10)

    def test_both_legs_are_on_the_grid(self):
        buy, sell = indicators.limit_band(7_432.0, 33.0)
        self.assertEqual(buy % indicators.tick_size(buy), 0)
        self.assertEqual(sell % indicators.tick_size(sell), 0)

    def test_no_volatility_means_no_band(self):
        self.assertEqual(indicators.limit_band(1_000.0, None), (None, None))
        self.assertEqual(indicators.limit_band(1_000.0, float("nan")), (None, None))

    def test_suspect_series_gets_no_band(self):
        idx = pd.bdate_range("2024-01-01", periods=320, tz="Asia/Tokyo")
        broken = pd.Series([300.0] * 300 + [30.0] * 20, index=idx)
        out = indicators.compute(broken)
        self.assertNotIn("buy_limit_1m", out)


if __name__ == "__main__":
    unittest.main(verbosity=2)
