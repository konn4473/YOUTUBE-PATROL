import os
import sys
import unittest

sys.path.append(os.getcwd())

from engine.watchlist_builder import WatchlistBuilder


class TestWatchlistBuilder(unittest.TestCase):
    def test_build_creates_theme_and_ticker_watchlist(self):
        builder = WatchlistBuilder(
            {
                "日本株": ["6501", "7203"],
                "原油": ["1605"],
            }
        )
        watchlist = builder.build(
            [
                {
                    "title": "日本株と原油が急変",
                    "channel": "Ch1",
                    "themes": ["日本株", "原油"],
                    "candidate_tickers": ["6501", "1605"],
                    "sentiment": {"score": -0.8},
                    "source": "search:日本株",
                },
                {
                    "title": "日本株を監視",
                    "channel": "Ch2",
                    "themes": ["日本株"],
                    "candidate_tickers": ["6501", "7203"],
                    "sentiment": {"score": 0.5},
                    "source": "search:日経平均",
                },
            ]
        )

        self.assertEqual(watchlist["overall_action"], "WATCH")
        self.assertIn("日本株", [item["name"] for item in watchlist["themes"]])
        self.assertTrue(any(item["ticker"] == "6501" for item in watchlist["tickers"]))


if __name__ == "__main__":
    unittest.main()
