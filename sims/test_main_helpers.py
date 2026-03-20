import os
import sys
import unittest

sys.path.append(os.getcwd())

from engine.main import (
    confirmed_by_price,
    filter_decisions_by_watchlist,
    shortlist_ai_proposals,
)


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

    def test_shortlist_ai_proposals_demotes_buy_without_confirmation(self):
        proposals = [
            {"ticker": "6501", "action": "BUY", "confidence": 0.82, "logic": "AI sees momentum"}
        ]
        watchlist = {"tickers": [{"ticker": "6501", "action": "WATCH"}]}
        market_data = {"6501": {"change_rate": 0.2}}
        news_data = []
        rules = {
            "buy_requires_price_confirmation": True,
            "min_price_confirmation_change_pct": 0.5,
            "ai_proposal_min_confidence": 0.55,
        }

        shortlisted = shortlist_ai_proposals(
            proposals,
            watchlist,
            market_data,
            news_data,
            [],
            rules,
        )

        self.assertEqual(shortlisted[0]["action"], "WATCH")

    def test_shortlist_ai_proposals_blocks_buy_when_watchlist_is_avoid(self):
        proposals = [
            {"ticker": "6501", "action": "BUY", "confidence": 0.82, "logic": "AI sees rebound"}
        ]
        watchlist = {"tickers": [{"ticker": "6501", "action": "AVOID"}]}

        shortlisted = shortlist_ai_proposals(
            proposals,
            watchlist,
            {"6501": {"change_rate": 1.1}},
            [],
            ["6501"],
            {"ai_proposal_min_confidence": 0.55},
        )

        self.assertEqual(shortlisted[0]["action"], "AVOID")

    def test_filter_decisions_blocks_buy_when_watchlist_is_avoid(self):
        decisions = [{"ticker": "6501", "action": "buy", "logic": "AI council buy"}]
        watchlist = {"tickers": [{"ticker": "6501", "action": "AVOID"}]}

        filtered = filter_decisions_by_watchlist(decisions, watchlist, ["6501"], {})

        self.assertEqual(filtered[0]["action"], "avoid")


if __name__ == "__main__":
    unittest.main()
