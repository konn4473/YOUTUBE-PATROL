import os
import sys
import unittest
from datetime import datetime
from unittest.mock import patch

sys.path.append(os.getcwd())

from engine import main as main_module
from engine.main import (
    build_runtime_config_snapshot,
    confirmed_by_price,
    filter_decisions_by_watchlist,
    main,
    select_active_watchlist,
    shortlist_ai_proposals,
)


class TestMainHelpers(unittest.TestCase):
    def test_main_passes_stale_watchlist_status_and_ai_runtime_to_store(self):
        saved_payload = {}

        class FakeCollector:
            def __init__(self, tickers):
                self.tickers = tickers

            def fetch_market_data(self):
                return {"6501": {"price": 1000, "change_rate": 1.0}}

            def fetch_news(self, feeds=None):
                return []

        class FakeAnalyzer:
            api_enabled = False
            proposal_model = "gemini-2.0-flash"
            council_model = "gemini-2.0-flash"
            sentiment_model = "gemini-2.5-flash-lite"

            def propose_trade_candidates(self, context):
                return []

            def consult_council(self, context):
                return []

            def build_runtime_info(self):
                return {
                    "api_enabled": False,
                    "sentiment_model": self.sentiment_model,
                    "proposal_model": self.proposal_model,
                    "council_model": self.council_model,
                    "sentiment_request_limit": 3,
                    "sentiment_requests_used": 0,
                    "cooldown_reason": None,
                }

        class FakeBroker:
            def __init__(self, data_dir="data"):
                self.portfolio = {"cash": 1000000, "holdings": {}}

            def monitor_and_execute(self, market_data):
                return []

            def place_order(self, **kwargs):
                raise AssertionError("place_order should not be called in this test")

        class FakePaperTracker:
            def __init__(self, data_dir="data"):
                pass

            def mark_to_market(self, market_data):
                return []

            def apply_shortlisted_candidates(self, shortlisted_candidates, market_data, risk_config=None):
                return []

            def record_signal_run(self, ai_proposals, shortlisted_candidates, market_data, final_decisions=None):
                return None

            def build_summary(self, market_data):
                return {"open_positions": 0, "closed_trades": 0, "total_pnl": 0}

        class FakePatrolStore:
            def __init__(self, data_dir="data"):
                pass

            def load_latest_watchlist(self):
                return {
                    "timestamp": "2026-03-23 00:00:00",
                    "tickers": [{"ticker": "6501", "action": "WATCH"}],
                }

            def save_run(self, payload):
                saved_payload.update(payload)
                return {
                    "report_path": "data/patrol/latest_report.md",
                    "history_path": "data/patrol/history/run.json",
                    "diff": {},
                    "snapshot": payload,
                }

            def notify_if_configured(self, result, webhook_url):
                return False

        config = {
            "target_tickers": ["6501"],
            "watchlist_rules": {
                "max_watchlist_age_hours": 24,
                "buy_requires_price_confirmation": True,
                "min_price_confirmation_change_pct": 0.5,
                "ai_proposal_min_confidence": 0.55,
            },
            "risk": {"default_stop_loss": 0.05, "default_profit_taking": 0.15},
            "enable_youtube_analysis": False,
            "youtube_patrol_targets": {},
            "youtube_max_videos": 1,
            "news_feeds": {},
        }

        with patch.object(main_module, "load_config", return_value=config), \
            patch.object(main_module, "DataCollector", FakeCollector), \
            patch.object(main_module, "AIAnalyzer", FakeAnalyzer), \
            patch.object(main_module, "MockBroker", FakeBroker), \
            patch.object(main_module, "PaperTradeTracker", FakePaperTracker), \
            patch.object(main_module, "PatrolStore", FakePatrolStore), \
            patch.object(main_module, "load_dotenv", lambda *args, **kwargs: None):
            main()

        self.assertEqual(saved_payload["watchlist"], {})
        self.assertIn("stale", saved_payload["watchlist_status"])
        self.assertFalse(saved_payload["ai_runtime"]["api_enabled"])
        self.assertEqual(saved_payload["runtime_config"]["max_watchlist_age_hours"], 24)

    def test_main_uses_fresh_watchlist_tickers_for_collection(self):
        saved_payload = {}
        collector_tickers = []

        class FakeCollector:
            def __init__(self, tickers):
                collector_tickers.extend(tickers)

            def fetch_market_data(self):
                return {
                    "6501": {"price": 1000, "change_rate": 1.0},
                    "8035": {"price": 2000, "change_rate": 0.8},
                }

            def fetch_news(self, feeds=None):
                return []

        class FakeAnalyzer:
            api_enabled = False
            proposal_model = "gemini-2.0-flash"
            council_model = "gemini-2.0-flash"
            sentiment_model = "gemini-2.5-flash-lite"

            def propose_trade_candidates(self, context):
                return []

            def consult_council(self, context):
                return []

            def build_runtime_info(self):
                return {
                    "api_enabled": False,
                    "sentiment_model": self.sentiment_model,
                    "proposal_model": self.proposal_model,
                    "council_model": self.council_model,
                    "sentiment_request_limit": 3,
                    "sentiment_requests_used": 0,
                    "cooldown_reason": None,
                }

        class FakeBroker:
            def __init__(self, data_dir="data"):
                self.portfolio = {"cash": 1000000, "holdings": {}}

            def monitor_and_execute(self, market_data):
                return []

            def place_order(self, **kwargs):
                raise AssertionError("place_order should not be called in this test")

        class FakePaperTracker:
            def __init__(self, data_dir="data"):
                pass

            def mark_to_market(self, market_data):
                return []

            def apply_shortlisted_candidates(self, shortlisted_candidates, market_data, risk_config=None):
                return []

            def record_signal_run(self, ai_proposals, shortlisted_candidates, market_data, final_decisions=None):
                return None

            def build_summary(self, market_data):
                return {"open_positions": 0, "closed_trades": 0, "total_pnl": 0}

        class FakePatrolStore:
            def __init__(self, data_dir="data"):
                pass

            def load_latest_watchlist(self):
                return {
                    "timestamp": "2026-03-25 07:00:00",
                    "overall_action": "WATCH",
                    "tickers": [{"ticker": "8035", "action": "WATCH"}],
                }

            def save_run(self, payload):
                saved_payload.update(payload)
                return {
                    "report_path": "data/patrol/latest_report.md",
                    "history_path": "data/patrol/history/run.json",
                    "diff": {},
                    "snapshot": payload,
                }

            def notify_if_configured(self, result, webhook_url):
                return False

        config = {
            "target_tickers": ["6501"],
            "watchlist_rules": {
                "max_watchlist_age_hours": 72,
                "buy_requires_price_confirmation": True,
                "min_price_confirmation_change_pct": 0.5,
                "ai_proposal_min_confidence": 0.55,
            },
            "risk": {"default_stop_loss": 0.05, "default_profit_taking": 0.15},
            "enable_youtube_analysis": False,
            "youtube_patrol_targets": {},
            "youtube_max_videos": 1,
            "news_feeds": {},
        }

        with patch.object(main_module, "load_config", return_value=config), \
            patch.object(main_module, "DataCollector", FakeCollector), \
            patch.object(main_module, "AIAnalyzer", FakeAnalyzer), \
            patch.object(main_module, "MockBroker", FakeBroker), \
            patch.object(main_module, "PaperTradeTracker", FakePaperTracker), \
            patch.object(main_module, "PatrolStore", FakePatrolStore), \
            patch.object(main_module, "load_dotenv", lambda *args, **kwargs: None):
            main()

        self.assertEqual(collector_tickers, ["6501", "8035"])
        self.assertEqual(saved_payload["watchlist_status"], "fresh")
        self.assertEqual(saved_payload["watchlist"]["tickers"][0]["ticker"], "8035")
        self.assertEqual(saved_payload["watchlist"]["tickers"][0]["action"], "WATCH")
        self.assertEqual(saved_payload["watchlist"]["overall_action"], "WATCH")
        self.assertEqual(saved_payload["runtime_config"]["youtube_max_videos"], 1)
        self.assertEqual(saved_payload["runtime_config"]["youtube_max_items"], None)

    def test_build_runtime_config_snapshot_extracts_operational_settings(self):
        runtime_config = build_runtime_config_snapshot(
            {
                "youtube_max_videos": 1,
                "enable_youtube_analysis": False,
                "enable_youtube_job": True,
                "youtube_patrol_targets": {
                    "recent_hours": 24,
                    "max_items": 20,
                    "use_transcripts": False,
                    "parallel_workers": 2,
                },
                "watchlist_rules": {
                    "max_watchlist_age_hours": 36,
                    "buy_requires_price_confirmation": True,
                    "min_price_confirmation_change_pct": 0.5,
                    "ai_proposal_min_confidence": 0.55,
                },
            }
        )

        self.assertEqual(runtime_config["youtube_max_videos"], 1)
        self.assertEqual(runtime_config["youtube_recent_hours"], 24)
        self.assertEqual(runtime_config["youtube_max_items"], 20)
        self.assertFalse(runtime_config["use_transcripts"])
        self.assertEqual(runtime_config["parallel_workers"], 2)
        self.assertEqual(runtime_config["max_watchlist_age_hours"], 36)
        self.assertTrue(runtime_config["buy_requires_price_confirmation"])
        self.assertEqual(runtime_config["min_price_confirmation_change_pct"], 0.5)
        self.assertEqual(runtime_config["ai_proposal_min_confidence"], 0.55)

    def test_main_includes_current_run_stage_actions_in_paper_trade_summary(self):
        saved_payload = {}

        class FakeCollector:
            def __init__(self, tickers):
                self.tickers = tickers

            def fetch_market_data(self):
                return {"6501": {"price": 1000, "change_rate": 1.2}}

            def fetch_news(self, feeds=None):
                return [{"source": "Reuters", "title": "Factory orders rise", "published": "2026-03-25"}]

        class FakeAnalyzer:
            api_enabled = False
            proposal_model = "gemini-2.0-flash"
            council_model = "gemini-2.0-flash"
            sentiment_model = "gemini-2.5-flash-lite"

            def propose_trade_candidates(self, context):
                return [{"ticker": "6501", "action": "WATCH", "confidence": 0.8, "logic": "AI idea"}]

            def consult_council(self, context):
                return [{"ticker": "6501", "action": "buy", "confidence": 0.7, "logic": "Council idea"}]

            def build_runtime_info(self):
                return {
                    "api_enabled": False,
                    "sentiment_model": self.sentiment_model,
                    "proposal_model": self.proposal_model,
                    "council_model": self.council_model,
                    "sentiment_request_limit": 3,
                    "sentiment_requests_used": 0,
                    "cooldown_reason": None,
                }

        class FakeBroker:
            def __init__(self, data_dir="data"):
                self.portfolio = {"cash": 1000000, "holdings": {}}

            def monitor_and_execute(self, market_data):
                return []

            def place_order(self, **kwargs):
                return None

        class FakePaperTracker:
            def __init__(self, data_dir="data"):
                self.recent_proposal_actions = []
                self.recent_final_actions = []

            def mark_to_market(self, market_data):
                return []

            def apply_shortlisted_candidates(self, shortlisted_candidates, market_data, risk_config=None):
                return []

            def record_signal_run(self, ai_proposals, shortlisted_candidates, market_data, final_decisions=None):
                self.recent_proposal_actions = [
                    f"{item.get('ticker')}:{item.get('action')}" for item in ai_proposals
                ]
                self.recent_final_actions = [
                    f"{item.get('ticker')}:{item.get('action')}" for item in (final_decisions or [])
                ]
                return None

            def build_summary(self, market_data):
                return {
                    "open_positions": 0,
                    "closed_trades": 0,
                    "total_pnl": 0,
                    "recent_proposal_actions": self.recent_proposal_actions,
                    "recent_final_actions": self.recent_final_actions,
                }

        class FakePatrolStore:
            def __init__(self, data_dir="data"):
                pass

            def load_latest_watchlist(self):
                return {
                    "timestamp": "2026-03-25 07:00:00",
                    "overall_action": "WATCH",
                    "tickers": [{"ticker": "6501", "action": "WATCH"}],
                }

            def save_run(self, payload):
                saved_payload.update(payload)
                return {
                    "report_path": "data/patrol/latest_report.md",
                    "history_path": "data/patrol/history/run.json",
                    "diff": {},
                    "snapshot": payload,
                }

            def notify_if_configured(self, result, webhook_url):
                return False

        config = {
            "target_tickers": ["6501"],
            "watchlist_rules": {
                "max_watchlist_age_hours": 72,
                "buy_requires_price_confirmation": False,
                "min_price_confirmation_change_pct": 0.5,
                "ai_proposal_min_confidence": 0.55,
            },
            "risk": {"default_stop_loss": 0.05, "default_profit_taking": 0.15},
            "enable_youtube_analysis": False,
            "youtube_patrol_targets": {},
            "youtube_max_videos": 1,
            "news_feeds": {},
        }

        with patch.object(main_module, "load_config", return_value=config), \
            patch.object(main_module, "DataCollector", FakeCollector), \
            patch.object(main_module, "AIAnalyzer", FakeAnalyzer), \
            patch.object(main_module, "MockBroker", FakeBroker), \
            patch.object(main_module, "PaperTradeTracker", FakePaperTracker), \
            patch.object(main_module, "PatrolStore", FakePatrolStore), \
            patch.object(main_module, "load_dotenv", lambda *args, **kwargs: None):
            main()

        self.assertEqual(
            saved_payload["paper_trade_summary"]["recent_proposal_actions"],
            ["6501:WATCH"],
        )
        self.assertEqual(
            saved_payload["paper_trade_summary"]["recent_final_actions"],
            ["6501:buy"],
        )

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

    def test_shortlist_ai_proposals_skips_low_confidence_items(self):
        proposals = [
            {"ticker": "6501", "action": "BUY", "confidence": 0.40, "logic": "weak"},
            {"ticker": "7203", "action": "WATCH", "confidence": 0.70, "logic": "ok"},
        ]

        shortlisted = shortlist_ai_proposals(
            proposals,
            {"tickers": []},
            {"6501": {"change_rate": 1.0}, "7203": {"change_rate": 0.3}},
            [],
            [],
            {"ai_proposal_min_confidence": 0.55},
        )

        self.assertEqual([item["ticker"] for item in shortlisted], ["7203"])

    def test_filter_decisions_keeps_sell_action_when_confirmation_is_missing(self):
        decisions = [{"ticker": "6501", "action": "sell", "logic": "take profit"}]
        watchlist = {"tickers": [{"ticker": "6501", "action": "WATCH"}]}

        filtered = filter_decisions_by_watchlist(
            decisions,
            watchlist,
            [],
            {"buy_requires_price_confirmation": True},
        )

        self.assertEqual(filtered[0]["action"], "sell")

    def test_select_active_watchlist_keeps_fresh_watchlist(self):
        watchlist = {
            "timestamp": "2026-03-25 07:00:00",
            "tickers": [{"ticker": "6501", "action": "WATCH"}],
        }

        active, status = select_active_watchlist(
            watchlist,
            {"max_watchlist_age_hours": 36},
            now=datetime(2026, 3, 25, 8, 0, 0),
        )

        self.assertEqual(status, "fresh")
        self.assertEqual(active["tickers"][0]["ticker"], "6501")

    def test_select_active_watchlist_drops_stale_watchlist(self):
        watchlist = {
            "timestamp": "2026-03-23 18:00:00",
            "tickers": [{"ticker": "6501", "action": "WATCH"}],
        }

        active, status = select_active_watchlist(
            watchlist,
            {"max_watchlist_age_hours": 24},
            now=datetime(2026, 3, 25, 8, 0, 0),
        )

        self.assertEqual(active, {})
        self.assertIn("stale", status)

    def test_select_active_watchlist_drops_watchlist_without_timestamp(self):
        active, status = select_active_watchlist(
            {"tickers": [{"ticker": "6501", "action": "WATCH"}]},
            {"max_watchlist_age_hours": 36},
            now=datetime(2026, 3, 25, 8, 0, 0),
        )

        self.assertEqual(active, {})
        self.assertEqual(status, "stale (missing timestamp)")


if __name__ == "__main__":
    unittest.main()
