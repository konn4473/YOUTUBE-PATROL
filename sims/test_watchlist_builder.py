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
            },
            rules={"top_ticker_limit": 10, "min_distinct_channels": 1, "min_distinct_groups": 2},
        )
        watchlist = builder.build(
            [
                {
                    "title": "日本株と原油が急変",
                    "channel": "Ch1",
                    "channel_group": "market_news",
                    "group_list": ["market_news", "search"],
                    "channel_weight": 1.2,
                    "themes": ["日本株", "原油"],
                    "candidate_tickers": ["6501", "1605"],
                    "sentiment": {"score": -0.8},
                    "source": "search:日本株",
                    "source_list": ["channel:Ch1", "search:日本株"],
                },
                {
                    "title": "日本株を監視",
                    "channel": "Ch2",
                    "channel_group": "stock_commentary",
                    "group_list": ["stock_commentary", "search"],
                    "channel_weight": 1.1,
                    "themes": ["日本株"],
                    "candidate_tickers": ["6501", "7203"],
                    "sentiment": {"score": 0.5},
                    "source": "search:日経平均",
                    "source_list": ["channel:Ch2", "search:日経平均"],
                },
            ]
        )

        self.assertEqual(watchlist["overall_action"], "WATCH")
        self.assertIn("日本株", [item["name"] for item in watchlist["themes"]])
        self.assertTrue(any(item["ticker"] == "6501" for item in watchlist["tickers"]))
        self.assertTrue(any(item["group_count"] >= 2 for item in watchlist["tickers"]))
        self.assertEqual(watchlist["source_summary"]["search_items"], 2)
        self.assertEqual(watchlist["source_summary"]["fixed_channel_items"], 2)
        top_theme = watchlist["themes"][0]
        self.assertIn("fixed_source_count", top_theme)
        self.assertIn("search_source_count", top_theme)
        self.assertIn("top_fixed_channels", top_theme)
        self.assertEqual(top_theme["top_fixed_channels"][0]["name"], "Ch1")
        top_ticker = next(item for item in watchlist["tickers"] if item["ticker"] == "6501")
        self.assertEqual(top_ticker["fixed_source_count"], 2)
        self.assertEqual(top_ticker["search_source_count"], 2)
        self.assertIn("top_fixed_channels", top_ticker)


if __name__ == "__main__":
    unittest.main()
