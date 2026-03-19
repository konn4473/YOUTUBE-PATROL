import os
import sys
import unittest

sys.path.append(os.getcwd())

from engine.youtube_analyzer import YouTubeAnalyzer


class FakeYouTubeAnalyzer(YouTubeAnalyzer):
    def __init__(self, targets, channel_items, search_items):
        super().__init__(targets, max_videos=3)
        self._channel_items = channel_items
        self._search_items = search_items

    def _extract_channel_videos(self, channel_url):
        return list(self._channel_items)

    def _search_videos(self, keyword):
        return list(self._search_items)


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
                    "published": "20260319",
                    "description": "",
                },
                {
                    "video_id": "both-sources",
                    "title": "固定と検索で重複",
                    "channel": "Fixed Channel",
                    "published": "20260318",
                    "description": "",
                },
            ],
            search_items=[
                {
                    "video_id": "both-sources",
                    "title": "固定と検索で重複",
                    "channel": "Fixed Channel",
                    "published": "20260318",
                    "description": "",
                },
                {
                    "video_id": "search-only",
                    "title": "検索だけの動画",
                    "channel": "Search Channel",
                    "published": "20260317",
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


if __name__ == "__main__":
    unittest.main()
