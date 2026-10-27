import unittest

import pandas as pd

from analysis.backtest import run_backtest


class BacktestTests(unittest.TestCase):
    def setUp(self):
        self.data = pd.DataFrame(
            {
                "date": pd.date_range("2024-01-01", periods=8, freq="D"),
                "close_price": [100, 110, 121, 115, 120, 118, 125, 130],
                "signal": ["Buy", "Hold", "Hold", "Sell", "Hold", "Buy", "Hold", "Sell"],
            }
        )

    def test_signal_is_applied_one_bar_later(self):
        frame, _ = run_backtest(self.data, commission_bps=0, slippage_bps=0)
        self.assertEqual(frame["position"].iloc[0], 0.0)
        self.assertEqual(frame["strategy_return"].iloc[0], 0.0)
        self.assertEqual(frame["position"].iloc[1], 1.0)
        self.assertAlmostEqual(frame["strategy_return"].iloc[1], 0.10)

    def test_costs_reduce_equity(self):
        _, free = run_backtest(self.data, commission_bps=0, slippage_bps=0)
        _, costly = run_backtest(self.data, commission_bps=15, slippage_bps=10)
        self.assertLess(costly["full_period"]["total_return"], free["full_period"]["total_return"])

    def test_time_split_is_reported(self):
        _, summary = run_backtest(
            self.data,
            commission_bps=0,
            slippage_bps=0,
            evaluation_start="2024-01-05",
        )
        self.assertEqual(summary["time_split"]["development"]["observations"], 4)
        self.assertEqual(summary["time_split"]["evaluation"]["observations"], 4)

    def test_negative_cost_is_rejected(self):
        with self.assertRaises(ValueError):
            run_backtest(self.data, commission_bps=-1)


if __name__ == "__main__":
    unittest.main()

