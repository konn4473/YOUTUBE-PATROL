import os
import shutil
import sys
import tempfile
import unittest

sys.path.append(os.getcwd())

from engine.paper_trade_tracker import PaperTradeTracker


class TestPaperTradeTracker(unittest.TestCase):
    def setUp(self):
        self.test_data_dir = tempfile.mkdtemp(prefix="yt_patrol_paper_", dir="data")
        self.tracker = PaperTradeTracker(data_dir=self.test_data_dir)

    def tearDown(self):
        shutil.rmtree(self.test_data_dir, ignore_errors=True)

    def test_buy_signal_opens_position_and_summary_updates(self):
        market_data = {"6501": {"price": 1000}}
        events = self.tracker.apply_shortlisted_candidates(
            [{"ticker": "6501", "action": "BUY", "confidence": 0.8, "logic": "test buy"}],
            market_data,
            {"default_stop_loss": 0.05, "default_profit_taking": 0.15},
            timestamp="2026-03-16 07:30:00",
        )

        summary = self.tracker.build_summary(market_data)

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["event"], "open")
        self.assertEqual(summary["open_positions"], 1)
        self.assertEqual(summary["closed_trades"], 0)

    def test_sell_signal_closes_position_and_realized_pnl_updates(self):
        self.tracker.apply_shortlisted_candidates(
            [{"ticker": "6501", "action": "BUY", "confidence": 0.8, "logic": "open"}],
            {"6501": {"price": 1000}},
            {"default_stop_loss": 0.05, "default_profit_taking": 0.15},
            timestamp="2026-03-16 07:30:00",
        )

        events = self.tracker.apply_shortlisted_candidates(
            [{"ticker": "6501", "action": "SELL", "confidence": 0.8, "logic": "close"}],
            {"6501": {"price": 1100}},
            {"default_stop_loss": 0.05, "default_profit_taking": 0.15},
            timestamp="2026-03-16 08:30:00",
        )
        summary = self.tracker.build_summary({"6501": {"price": 1100}})

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["event"], "close")
        self.assertEqual(events[0]["realized_pnl"], 10000.0)
        self.assertEqual(summary["open_positions"], 0)
        self.assertEqual(summary["closed_trades"], 1)
        self.assertEqual(summary["realized_pnl"], 10000.0)
        self.assertEqual(summary["win_rate"], 100.0)
        self.assertGreaterEqual(summary["average_holding_days"], 0.0)
        self.assertIn("holding_days", events[0])

    def test_record_signal_run_keeps_recent_history(self):
        self.tracker.record_signal_run(
            [{"ticker": "6501", "action": "WATCH"}],
            [{"ticker": "6501", "action": "WATCH", "confidence": 0.6}],
            {"6501": {"price": 1000, "change_rate": 1.2}},
            timestamp="2026-03-16 07:30:00",
        )

        self.assertEqual(len(self.tracker.signals), 1)
        self.assertEqual(self.tracker.signals[0]["market_prices"]["6501"]["price"], 1000)

    def test_summary_includes_holding_days_and_recent_signal_actions(self):
        self.tracker.record_signal_run(
            [{"ticker": "6501", "action": "WATCH"}],
            [{"ticker": "6501", "action": "BUY", "confidence": 0.7}],
            {"6501": {"price": 1000, "change_rate": 1.0}},
            timestamp="2026-03-16 07:30:00",
        )
        self.tracker.apply_shortlisted_candidates(
            [{"ticker": "6501", "action": "BUY", "confidence": 0.8, "logic": "open"}],
            {"6501": {"price": 1000}},
            {"default_stop_loss": 0.05, "default_profit_taking": 0.15},
            timestamp="2026-03-16 07:30:00",
        )

        summary = self.tracker.build_summary({"6501": {"price": 1020}})

        self.assertEqual(summary["open_positions"], 1)
        self.assertIn("holding_days", summary["positions"][0])
        self.assertIn("6501:BUY", summary["recent_signal_actions"])

    def test_summary_includes_streaks_and_ticker_pnl(self):
        self.tracker.apply_shortlisted_candidates(
            [{"ticker": "6501", "action": "BUY", "confidence": 0.8, "logic": "open"}],
            {"6501": {"price": 1000}},
            {"default_stop_loss": 0.05, "default_profit_taking": 0.15},
            timestamp="2026-03-16 07:30:00",
        )
        self.tracker.apply_shortlisted_candidates(
            [{"ticker": "6501", "action": "SELL", "confidence": 0.8, "logic": "close"}],
            {"6501": {"price": 1100}},
            {"default_stop_loss": 0.05, "default_profit_taking": 0.15},
            timestamp="2026-03-16 08:30:00",
        )
        self.tracker.apply_shortlisted_candidates(
            [{"ticker": "7203", "action": "BUY", "confidence": 0.8, "logic": "open"}],
            {"7203": {"price": 1000}},
            {"default_stop_loss": 0.05, "default_profit_taking": 0.15},
            timestamp="2026-03-16 09:30:00",
        )
        self.tracker.apply_shortlisted_candidates(
            [{"ticker": "7203", "action": "SELL", "confidence": 0.8, "logic": "close"}],
            {"7203": {"price": 900}},
            {"default_stop_loss": 0.05, "default_profit_taking": 0.15},
            timestamp="2026-03-16 10:30:00",
        )

        summary = self.tracker.build_summary({"6501": {"price": 1100}, "7203": {"price": 900}})

        self.assertEqual(summary["best_win_streak"], 1)
        self.assertEqual(summary["best_loss_streak"], 1)
        self.assertTrue(any(item["ticker"] == "6501" for item in summary["ticker_pnl"]))


if __name__ == "__main__":
    unittest.main()
