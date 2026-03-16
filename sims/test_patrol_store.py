import os
import shutil
import sys
import tempfile
import unittest

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
                "decisions": [{"ticker": "6501", "action": "wait", "confidence": 50}],
                "portfolio": {"cash": 1000000, "holdings": {}},
            }
        )

        self.assertTrue(os.path.exists(first["report_path"]))
        self.assertTrue(os.path.exists(second["history_path"]))
        self.assertEqual(second["diff"]["new_news_count"], 1)
        self.assertEqual(second["diff"]["new_youtube_count"], 1)
        self.assertEqual(second["diff"]["decision_count"], 1)

    def test_youtube_notification_text_includes_action(self):
        watchlist = {
            "timestamp": "2026-01-02 07:30:00",
            "overall_action": "AVOID",
            "themes": [{"name": "日本株"}, {"name": "原油"}],
            "tickers": [{"ticker": "1605", "action": "AVOID"}],
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
        self.assertIn("候補銘柄: 1605(見送り)", text)
        self.assertIn("補足: YouTube 単独では買いシグナルにしません。", text)

    def test_main_notification_text_includes_action(self):
        result = self.store.save_run(
            {
                "market": {"6501": {"price": 101.0}},
                "news": [{"source": "Reuters", "title": "Factory orders rise", "published": "2026-01-02"}],
                "youtube": [],
                "decisions": [{"ticker": "6501", "action": "buy", "confidence": 72}],
                "portfolio": {"cash": 1000000, "holdings": {}},
            }
        )
        text = self.store._build_notification_text(result)

        self.assertIn("行動: 買い", text)
        self.assertIn("判断: 6501 買い 信頼度=72", text)
        self.assertIn("補足: 注文前に値動きとリスク上限を必ず確認してください。", text)


if __name__ == "__main__":
    unittest.main()
