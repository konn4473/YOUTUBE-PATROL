import os
import sys
import unittest
from datetime import datetime, timedelta

sys.path.append(os.getcwd())

from engine.analyzer import AIAnalyzer
from engine.youtube_analyzer import YouTubeAnalyzer


def _days_ago_text(days):
    return (datetime.utcnow() - timedelta(days=days)).strftime("%Y%m%d")


class FakeYouTubeAnalyzer(YouTubeAnalyzer):
    def __init__(self, targets, channel_items, search_items):
        super().__init__(targets, max_videos=3)
        self._channel_items = channel_items
        self._search_items = search_items

    def _extract_channel_videos(self, channel_url):
        return list(self._channel_items)

    def _search_videos(self, keyword):
        return list(self._search_items)


class TranscriptTrackingAnalyzer(FakeYouTubeAnalyzer):
    def __init__(self, targets, channel_items, search_items):
        super().__init__(targets, channel_items, search_items)
        self.transcript_calls = 0

    def _fetch_transcript(self, video_id):
        self.transcript_calls += 1
        return "transcript text"


class SharedSentimentAnalyzer:
    def __init__(self):
        self.shared_sentiment_result = {
            "score": 0.0,
            "reason": "gemini cooldown active (60s remaining)",
        }
        self.calls = 0
        self.sequential_sentiment_mode = True

    def analyze_sentiment(self, text):
        self.calls += 1
        return {"score": 0.5, "reason": "should not be used"}


class TestYouTubeAnalyzer(unittest.TestCase):
    def test_collect_targets_merges_sources_and_prefers_recent_fixed_items(self):
        analyzer = FakeYouTubeAnalyzer(
            {
                "channels": [{"name": "Fixed Channel", "url": "https://example.com"}],
                "search_keywords": ["日本株"],
                "max_items": 2,
                "recent_hours": 72,
            },
            channel_items=[
                {
                    "video_id": "fixed-new",
                    "title": "新しい固定動画",
                    "channel": "Fixed Channel",
                    "published": _days_ago_text(0),
                    "description": "",
                },
                {
                    "video_id": "both-sources",
                    "title": "固定と検索で重複",
                    "channel": "Fixed Channel",
                    "published": _days_ago_text(1),
                    "description": "",
                },
            ],
            search_items=[
                {
                    "video_id": "both-sources",
                    "title": "固定と検索で重複",
                    "channel": "Fixed Channel",
                    "published": _days_ago_text(1),
                    "description": "",
                },
                {
                    "video_id": "search-only",
                    "title": "検索だけの動画",
                    "channel": "Search Channel",
                    "published": _days_ago_text(2),
                    "description": "",
                },
            ],
        )

        items = analyzer.collect_targets()

        self.assertEqual([item["video_id"] for item in items], ["fixed-new", "both-sources"])
        self.assertEqual(
            items[1]["source_list"],
            ["channel:Fixed Channel", "search:日本株"],
        )
        self.assertEqual(items[1]["group_list"], ["channel", "search"])

    def test_analyze_reuses_shared_sentiment_result_without_per_video_calls(self):
        analyzer = TranscriptTrackingAnalyzer(
            {
                "channels": [{"name": "Fixed Channel", "url": "https://example.com"}],
                "search_keywords": [],
                "max_items": 1,
                "recent_hours": 72,
                "use_transcripts": True,
            },
            channel_items=[
                {
                    "video_id": "fixed-new",
                    "title": "新しい固定動画",
                    "channel": "Fixed Channel",
                    "published": _days_ago_text(0),
                    "description": "",
                }
            ],
            search_items=[],
        )
        ai_analyzer = SharedSentimentAnalyzer()

        items = analyzer.analyze(ai_analyzer)

        self.assertEqual(ai_analyzer.calls, 0)
        self.assertEqual(analyzer.transcript_calls, 0)
        self.assertEqual(items[0]["sentiment"]["reason"], "gemini cooldown active (60s remaining)")

    def test_ai_analyzer_caps_sentiment_requests(self):
        analyzer = AIAnalyzer()
        analyzer.api_enabled = True
        analyzer.sentiment_request_limit = 1
        analyzer.api_key = "test-key"
        analyzer._generate_content = lambda model, prompt: '{"score": 0.4, "reason": "ok"}'

        first = analyzer.analyze_sentiment("first")
        second = analyzer.analyze_sentiment("second")

        self.assertEqual(first["score"], 0.4)
        self.assertIn("budget reached", second["reason"])

    def test_ai_analyzer_uses_flash_lite_for_sentiment(self):
        analyzer = AIAnalyzer()
        analyzer.api_enabled = True
        analyzer.api_key = "test-key"
        called = {}

        def fake_generate_content(model, prompt):
            called["model"] = model
            return '{"score": 0.4, "reason": "ok"}'

        analyzer._generate_content = fake_generate_content

        analyzer.analyze_sentiment("test")

        self.assertEqual(called["model"], "gemini-2.5-flash-lite")


if __name__ == "__main__":
    unittest.main()
