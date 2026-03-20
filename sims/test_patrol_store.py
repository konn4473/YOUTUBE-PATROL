import os
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.append(os.getcwd())

from engine.patrol_store import PatrolStore


class TestPatrolStore(unittest.TestCase):
    def setUp(self):
        self.test_data_dir = tempfile.mkdtemp(prefix="yt_patrol_store_", dir="data")
        self.store = PatrolStore(data_dir=self.test_data_dir)

    def tearDown(self):
        shutil.rmtree(self.test_data_dir, ignore_errors=True)

    def test_save_run_creates_snapshot_and_diff(self):
        first = self.store.save_run(
            {
                "market": {"6501": {"price": 100.0}},
                "news": [{"source": "Reuters", "title": "A", "published": "2026-01-01"}],
                "youtube": [],
                "decisions": [],
                "paper_trade_summary": {"open_positions": 0, "closed_trades": 0, "total_pnl": 0},
                "portfolio": {"cash": 1000000, "holdings": {}},
            }
        )
        second = self.store.save_run(
            {
                "market": {"6501": {"price": 101.0}},
                "news": [
                    {"source": "Reuters", "title": "A", "published": "2026-01-01"},
                    {"source": "Nikkei", "title": "B", "published": "2026-01-02"},
                ],
                "youtube": [
                    {"video_id": "vid1", "title": "Video", "channel": "Ch", "published": "2026-01-02"}
                ],
                "paper_trade_summary": {"open_positions": 1, "closed_trades": 0, "total_pnl": 1200},
                "decisions": [{"ticker": "6501", "action": "wait", "confidence": 50}],
                "portfolio": {"cash": 1000000, "holdings": {}},
            }
        )

        self.assertTrue(os.path.exists(first["report_path"]))
        self.assertTrue(os.path.exists(second["history_path"]))
        self.assertEqual(second["diff"]["new_news_count"], 1)
        self.assertEqual(second["diff"]["new_youtube_count"], 1)
        self.assertEqual(second["diff"]["decision_count"], 1)
        with open(second["report_path"], encoding="utf-8-sig") as f:
            self.assertIn("## Paper Trade Summary", f.read())

    def test_youtube_notification_text_includes_action(self):
        watchlist = {
            "timestamp": "2026-01-02 07:30:00",
            "overall_action": "AVOID",
            "themes": [{"name": "日本株"}, {"name": "原油"}],
            "tickers": [
                {
                    "ticker": "1605",
                    "action": "AVOID",
                    "fixed_source_count": 1,
                    "search_source_count": 2,
                }
            ],
        }
        result = self.store.save_youtube_run(
            [
                {
                    "video_id": "vid1",
                    "title": "日本株と原油の急変",
                    "channel": "Test Channel",
                    "source": "search:日本株",
                    "published": "2026-01-02",
                    "sentiment": {"score": -0.9, "reason": "WTI crude surge hurts Japan equities."},
                }
            ],
            watchlist=watchlist,
        )
        text = self.store._build_youtube_notification_text(result)

        self.assertIn("行動: 見送り", text)
        self.assertIn("テーマ: 日本株, 原油", text)
        self.assertIn("候補銘柄: 1605(見送り/固定1/検索2)", text)
        self.assertIn("補足: YouTube 単独では買いシグナルにしません。", text)

    def test_save_youtube_run_keeps_multi_source_fields(self):
        result = self.store.save_youtube_run(
            [
                {
                    "video_id": "vid-multi",
                    "title": "複数経路で検出",
                    "channel": "Test Channel",
                    "source": "channel:Test Channel",
                    "source_list": ["channel:Test Channel", "search:日本株"],
                    "published": "2026-01-02",
                    "channel_group": "market_news",
                    "group_list": ["market_news", "search"],
                    "sentiment": {"score": 0.4, "reason": "test"},
                    "themes": ["日本株"],
                    "candidate_tickers": ["6501"],
                    "confidence": 0.7,
                }
            ]
        )

        item = result["snapshot"]["youtube"][0]
        self.assertEqual(item["source_list"], ["channel:Test Channel", "search:日本株"])
        self.assertEqual(item["group_list"], ["market_news", "search"])

    def test_youtube_notification_triggers_on_watchlist_change_without_new_video(self):
        self.store.save_youtube_run(
            [
                {
                    "video_id": "vid1",
                    "title": "同じ動画",
                    "channel": "Test Channel",
                    "source": "channel:Test Channel",
                    "published": "2026-01-02",
                    "sentiment": {"score": 0.1, "reason": "test"},
                }
            ],
            watchlist={
                "timestamp": "2026-01-02 07:30:00",
                "overall_action": "NO SIGNAL",
                "themes": [],
                "tickers": [{"ticker": "6501", "action": "NO SIGNAL"}],
            },
        )

        result = self.store.save_youtube_run(
            [
                {
                    "video_id": "vid1",
                    "title": "同じ動画",
                    "channel": "Test Channel",
                    "source": "channel:Test Channel",
                    "published": "2026-01-02",
                    "sentiment": {"score": 0.1, "reason": "test"},
                }
            ],
            watchlist={
                "timestamp": "2026-01-03 07:30:00",
                "overall_action": "WATCH",
                "themes": [{"name": "日本株"}],
                "tickers": [{"ticker": "6501", "action": "WATCH"}],
            },
        )

        self.assertEqual(result["diff"]["new_youtube_count"], 0)
        self.assertTrue(result["diff"]["watchlist_action_changed"])
        with patch("engine.patrol_store.requests.post") as mock_post:
            self.assertTrue(
                self.store.notify_youtube_if_configured(
                    result, "https://example.com/webhook"
                )
            )
            mock_post.assert_called_once()

    def test_main_notification_text_includes_action_and_paper_trade_summary(self):
        result = self.store.save_run(
            {
                "market": {"6501": {"price": 101.0}},
                "news": [{"source": "Reuters", "title": "Factory orders rise", "published": "2026-01-02"}],
                "youtube": [],
                "paper_trade_summary": {
                    "open_positions": 1,
                    "closed_trades": 2,
                    "total_pnl": 3500,
                    "average_holding_days": 2.5,
                    "best_win_streak": 2,
                    "best_loss_streak": 1,
                    "ticker_pnl": [{"ticker": "6501", "realized_pnl": 3500}],
                    "recent_signal_actions": ["6501:BUY"],
                },
                "decisions": [{"ticker": "6501", "action": "buy", "confidence": 72}],
                "portfolio": {"cash": 1000000, "holdings": {}},
            }
        )
        text = self.store._build_notification_text(result)

        self.assertIn("行動: 買い", text)
        self.assertIn("紙上売買: 決済=2 保有=1 合計損益=3500", text)
        self.assertIn("紙上売買詳細: 平均保有日数=2.5 最近アクション=6501:BUY", text)
        self.assertIn("紙上売買連続記録: 連勝=2 連敗=1", text)
        self.assertIn("銘柄別損益: 6501=3500", text)
        self.assertIn("判断: 6501 買い 信頼度=72", text)
        self.assertIn("補足: 注文前に値動きとリスク上限を必ず確認してください。", text)

    def test_main_notification_triggers_on_confirmed_watch_or_ai_change(self):
        self.store.save_run(
            {
                "market": {"6501": {"price": 100.0}},
                "news": [],
                "youtube": [],
                "confirmed_watch_tickers": [],
                "ai_proposals": [],
                "decisions": [],
                "paper_trade_summary": {"open_positions": 0, "closed_trades": 0, "total_pnl": 0},
                "portfolio": {"cash": 1000000, "holdings": {}},
            }
        )
        result = self.store.save_run(
            {
                "market": {"6501": {"price": 101.0}},
                "news": [],
                "youtube": [],
                "confirmed_watch_tickers": ["6501"],
                "ai_proposals": [{"ticker": "6501", "action": "WATCH", "confidence": 0.7}],
                "decisions": [],
                "paper_trade_summary": {"open_positions": 0, "closed_trades": 0, "total_pnl": 0},
                "portfolio": {"cash": 1000000, "holdings": {}},
            }
        )

        self.assertTrue(result["diff"]["confirmed_watch_changed"])
        self.assertTrue(result["diff"]["top_ai_proposals_changed"])
        text = self.store._build_notification_text(result)
        self.assertIn("確認済み監視変化: なし → 6501", text)
        self.assertIn("AI提案変化: なし → 6501", text)
        with patch("engine.patrol_store.requests.post") as mock_post:
            self.assertTrue(
                self.store.notify_if_configured(result, "https://example.com/webhook")
            )
            mock_post.assert_called_once()

    def test_main_notification_triggers_on_shortlisted_change_without_new_items(self):
        self.store.save_run(
            {
                "market": {"6501": {"price": 100.0}},
                "news": [],
                "youtube": [],
                "confirmed_watch_tickers": [],
                "ai_proposals": [],
                "shortlisted_candidates": [],
                "decisions": [],
                "paper_trade_summary": {"open_positions": 0, "closed_trades": 0, "total_pnl": 0},
                "portfolio": {"cash": 1000000, "holdings": {}},
            }
        )
        result = self.store.save_run(
            {
                "market": {"6501": {"price": 101.0}},
                "news": [],
                "youtube": [],
                "confirmed_watch_tickers": [],
                "ai_proposals": [],
                "shortlisted_candidates": [{"ticker": "6501", "action": "WATCH", "confidence": 0.7}],
                "decisions": [],
                "paper_trade_summary": {"open_positions": 0, "closed_trades": 0, "total_pnl": 0},
                "portfolio": {"cash": 1000000, "holdings": {}},
            }
        )

        self.assertTrue(result["diff"]["top_shortlisted_changed"])
        text = self.store._build_notification_text(result)
        self.assertIn("候補絞り込み変化: なし → 6501:WATCH", text)
        with patch("engine.patrol_store.requests.post") as mock_post:
            self.assertTrue(
                self.store.notify_if_configured(result, "https://example.com/webhook")
            )
            mock_post.assert_called_once()

    def test_main_action_reports_avoid_when_only_avoid_proposals_exist(self):
        result = self.store.save_run(
            {
                "market": {"6501": {"price": 101.0}},
                "news": [],
                "youtube": [],
                "confirmed_watch_tickers": [],
                "ai_proposals": [{"ticker": "6501", "action": "AVOID", "confidence": 0.8}],
                "shortlisted_candidates": [],
                "decisions": [],
                "paper_trade_summary": {"open_positions": 0, "closed_trades": 0, "total_pnl": 0},
                "portfolio": {"cash": 1000000, "holdings": {}},
            }
        )

        text = self.store._build_notification_text(result)
        self.assertIn("行動: 見送り", text)


if __name__ == "__main__":
    unittest.main()
