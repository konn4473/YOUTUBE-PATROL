import json
import os
from datetime import datetime

import requests


class PatrolStore:
    def __init__(self, data_dir="data"):
        self.base_dir = os.path.join(data_dir, "patrol")
        self.history_dir = os.path.join(self.base_dir, "history")
        self.latest_snapshot_path = os.path.join(self.base_dir, "latest_snapshot.json")
        self.latest_report_path = os.path.join(self.base_dir, "latest_report.md")

        self.youtube_dir = os.path.join(data_dir, "youtube_patrol")
        self.youtube_history_dir = os.path.join(self.youtube_dir, "history")
        self.youtube_latest_snapshot_path = os.path.join(
            self.youtube_dir, "latest_snapshot.json"
        )
        self.youtube_latest_report_path = os.path.join(
            self.youtube_dir, "latest_report.md"
        )

        os.makedirs(self.history_dir, exist_ok=True)
        os.makedirs(self.youtube_history_dir, exist_ok=True)

    def save_run(self, payload):
        snapshot = self._build_snapshot(payload)
        previous = self.load_latest_snapshot()
        diff = self._build_diff(previous, snapshot)
        report = self._build_report(snapshot, diff)
        history_path = self._history_path(self.history_dir, snapshot["timestamp"])

        self._write_json(self.latest_snapshot_path, snapshot)
        self._write_json(history_path, snapshot)
        self._write_text(self.latest_report_path, report)

        return {
            "snapshot": snapshot,
            "diff": diff,
            "history_path": history_path,
            "report_path": self.latest_report_path,
        }

    def save_youtube_run(self, youtube_items):
        payload = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "youtube": [
                {
                    "id": self._youtube_id(item),
                    "title": item.get("title"),
                    "channel": item.get("channel"),
                    "source": item.get("source"),
                    "published": item.get("published"),
                    "sentiment": item.get("sentiment"),
                }
                for item in youtube_items
            ],
        }
        previous = self.load_latest_youtube_snapshot()
        diff = self._build_youtube_diff(previous, payload)
        report = self._build_youtube_report(payload, diff)
        history_path = self._history_path(self.youtube_history_dir, payload["timestamp"])

        self._write_json(self.youtube_latest_snapshot_path, payload)
        self._write_json(history_path, payload)
        self._write_text(self.youtube_latest_report_path, report)

        return {
            "snapshot": payload,
            "diff": diff,
            "history_path": history_path,
            "report_path": self.youtube_latest_report_path,
        }

    def load_latest_snapshot(self):
        return self._load_json(self.latest_snapshot_path)

    def load_latest_youtube_snapshot(self):
        return self._load_json(self.youtube_latest_snapshot_path)

    def notify_if_configured(self, result, webhook_url):
        if not self._is_valid_webhook_url(webhook_url):
            return False
        diff = result["diff"]
        interesting = (
            diff["new_news_count"] > 0
            or diff["new_youtube_count"] > 0
            or diff["decision_count"] > 0
        )
        if not interesting:
            return False
        content = self._build_notification_text(result)
        requests.post(webhook_url, json={"content": content}, timeout=10)
        return True

    def notify_youtube_if_configured(self, result, webhook_url):
        if not self._is_valid_webhook_url(webhook_url):
            return False
        diff = result["diff"]
        if diff["new_youtube_count"] <= 0:
            return False
        content = self._build_youtube_notification_text(result)
        requests.post(webhook_url, json={"content": content}, timeout=10)
        return True

    def _build_snapshot(self, payload):
        return {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "market": payload.get("market", {}),
            "news": [
                {
                    "id": self._news_id(item),
                    "source": item.get("source"),
                    "title": item.get("title"),
                    "published": item.get("published"),
                    "link": item.get("link"),
                }
                for item in payload.get("news", [])
            ],
            "youtube": [
                {
                    "id": self._youtube_id(item),
                    "title": item.get("title"),
                    "channel": item.get("channel"),
                    "source": item.get("source"),
                    "published": item.get("published"),
                    "sentiment": item.get("sentiment"),
                }
                for item in payload.get("youtube", [])
            ],
            "decisions": payload.get("decisions", []),
            "portfolio": payload.get("portfolio", {}),
        }

    def _build_diff(self, previous, current):
        previous_news_ids = set()
        previous_youtube_ids = set()
        if previous:
            previous_news_ids = {item["id"] for item in previous.get("news", [])}
            previous_youtube_ids = {item["id"] for item in previous.get("youtube", [])}

        new_news = [
            item for item in current.get("news", []) if item["id"] not in previous_news_ids
        ]
        new_youtube = [
            item
            for item in current.get("youtube", [])
            if item["id"] not in previous_youtube_ids
        ]

        return {
            "new_news_count": len(new_news),
            "new_youtube_count": len(new_youtube),
            "decision_count": len(current.get("decisions", [])),
            "new_news": new_news[:5],
            "new_youtube": new_youtube[:5],
        }

    def _build_youtube_diff(self, previous, current):
        previous_ids = set()
        if previous:
            previous_ids = {item["id"] for item in previous.get("youtube", [])}
        new_youtube = [
            item for item in current.get("youtube", []) if item["id"] not in previous_ids
        ]
        return {
            "new_youtube_count": len(new_youtube),
            "new_youtube": new_youtube[:5],
        }

    def _build_report(self, snapshot, diff):
        lines = [
            f"# Patrol Report {snapshot['timestamp']}",
            "",
            "## Summary",
            f"- Market tickers: {len(snapshot.get('market', {}))}",
            f"- News items: {len(snapshot.get('news', []))}",
            f"- YouTube items: {len(snapshot.get('youtube', []))}",
            f"- Decisions: {len(snapshot.get('decisions', []))}",
            f"- New news since last run: {diff['new_news_count']}",
            f"- New YouTube items since last run: {diff['new_youtube_count']}",
            "",
            "## New News",
        ]
        if diff["new_news"]:
            for item in diff["new_news"]:
                lines.append(
                    f"- [{item.get('source')}] {item.get('title')} ({item.get('published')})"
                )
        else:
            lines.append("- None")

        lines.extend(["", "## Market Snapshot"])
        if snapshot.get("market"):
            for ticker, item in snapshot["market"].items():
                lines.append(
                    f"- {ticker}: price={item.get('price')} change={item.get('change_rate')}%"
                )
        else:
            lines.append("- None")

        lines.extend(["", "## Decisions"])
        if snapshot.get("decisions"):
            for item in snapshot["decisions"]:
                lines.append(
                    f"- {item.get('ticker')}: {item.get('action')} ({item.get('confidence')})"
                )
        else:
            lines.append("- None")
        lines.append("")
        return "\n".join(lines)

    def _build_youtube_report(self, snapshot, diff):
        lines = [
            f"# YouTube Patrol Report {snapshot['timestamp']}",
            "",
            "## Summary",
            f"- YouTube items: {len(snapshot.get('youtube', []))}",
            f"- New YouTube items since last run: {diff['new_youtube_count']}",
            "",
            "## Latest YouTube Items",
        ]
        latest_items = snapshot.get("youtube", [])[:5]
        if latest_items:
            for item in latest_items:
                sentiment = item.get("sentiment") or {}
                lines.append(
                    f"- [{item.get('channel')}] {item.get('title')} "
                    f"(score={sentiment.get('score')}, published={item.get('published')})"
                )
        else:
            lines.append("- None")
        lines.extend(["", "## New YouTube Since Last Run"])
        if diff["new_youtube"]:
            for item in diff["new_youtube"]:
                lines.append(f"- [{item.get('channel')}] {item.get('title')}")
        else:
            lines.append("- None")
        lines.append("")
        return "\n".join(lines)

    def _build_notification_text(self, result):
        diff = result["diff"]
        lines = [
            "Patrol update",
            f"- new_news: {diff['new_news_count']}",
            f"- new_youtube: {diff['new_youtube_count']}",
            f"- decisions: {diff['decision_count']}",
        ]
        for item in diff["new_news"][:3]:
            lines.append(f"- news: [{item.get('source')}] {item.get('title')}")
        return "\n".join(lines)

    def _build_youtube_notification_text(self, result):
        diff = result["diff"]
        lines = [
            "YouTube patrol update",
            f"- new_youtube: {diff['new_youtube_count']}",
        ]
        for item in diff["new_youtube"][:3]:
            sentiment = item.get("sentiment") or {}
            lines.append(
                f"- [{item.get('channel')}] {item.get('title')} score={sentiment.get('score')}"
            )
        return "\n".join(lines)

    def _load_json(self, path):
        if not os.path.exists(path):
            return None
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _write_json(self, path, payload):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)

    def _write_text(self, path, text):
        with open(path, "w", encoding="utf-8-sig") as f:
            f.write(text)

    def _history_path(self, history_dir, timestamp):
        safe = timestamp.replace(":", "").replace("-", "").replace(" ", "_")
        return os.path.join(history_dir, f"run_{safe}.json")

    def _is_valid_webhook_url(self, webhook_url):
        if not webhook_url:
            return False
        if webhook_url == "your_discord_webhook_url_here":
            return False
        return webhook_url.startswith("http://") or webhook_url.startswith("https://")

    def _news_id(self, item):
        return f"{item.get('source', '')}|{item.get('title', '')}|{item.get('published', '')}"

    def _youtube_id(self, item):
        if item.get("video_id"):
            return item["video_id"]
        return f"{item.get('channel', '')}|{item.get('title', '')}|{item.get('published', '')}"
