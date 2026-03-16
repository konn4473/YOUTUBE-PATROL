import os
import sys
import unittest

sys.path.append(os.getcwd())

from engine.main import confirmed_by_price, filter_decisions_by_watchlist


class TestMainHelpers(unittest.TestCase):
    def test_confirmed_by_price(self):
        watchlist = {
            "tickers": [
                {"ticker": "6501", "action": "WATCH"},
                {"ticker": "7203", "action": "WATCH"},
            ]
        }
        market_data = {
            "6501": {"change_rate": 1.2},
            "7203": {"change_rate": 0.1},
        }
        rules = {"buy_requires_price_confirmation": True, "min_price_confirmation_change_pct": 0.5}

        confirmed = confirmed_by_price(watchlist, market_data, rules)

        self.assertEqual(confirmed, ["6501"])

    def test_filter_decisions_by_watchlist(self):
        decisions = [
            {"ticker": "6501", "action": "buy", "logic": "watchlist support"},
            {"ticker": "8035", "action": "buy", "logic": "other"},
        ]
        watchlist = {"tickers": [{"ticker": "6501", "action": "WATCH"}]}
        rules = {"buy_requires_price_confirmation": True}

        filtered = filter_decisions_by_watchlist(decisions, watchlist, [], rules)

        self.assertEqual(filtered[0]["action"], "watch")
        self.assertEqual(filtered[1]["action"], "buy")


if __name__ == "__main__":
    unittest.main()
