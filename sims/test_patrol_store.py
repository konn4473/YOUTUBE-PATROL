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
            ]
        )
        text = self.store._build_youtube_notification_text(result)

        self.assertIn("Action: AVOID", text)
        self.assertIn("Themes: 日本株, 原油", text)
        self.assertIn("Trading note: YouTube alone is not a buy signal.", text)

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

        self.assertIn("Action: BUY", text)
        self.assertIn("Decision: 6501 buy confidence=72", text)
        self.assertIn("Trading note: Confirm with price action and risk limits before any order.", text)


if __name__ == "__main__":
    unittest.main()
