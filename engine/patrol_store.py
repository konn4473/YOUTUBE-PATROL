import json
import os
from datetime import datetime

import requests

from engine.external_store import ExternalStore


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
        self.watchlist_latest_path = os.path.join(
            self.youtube_dir, "latest_watchlist.json"
        )
        self.watchlist_report_path = os.path.join(
            self.youtube_dir, "watchlist_report.md"
        )
        self.external_store = ExternalStore()

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
        uploads = self.external_store.upload_files(
            [self.latest_snapshot_path, history_path, self.latest_report_path]
        )

        return {
            "snapshot": snapshot,
            "diff": diff,
            "history_path": history_path,
            "report_path": self.latest_report_path,
            "uploads": uploads,
        }

    def save_youtube_run(self, youtube_items, watchlist=None):
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
                    "themes": item.get("themes", []),
                    "candidate_tickers": item.get("candidate_tickers", []),
                    "confidence": item.get("confidence"),
                }
                for item in youtube_items
            ],
        }
        watchlist = watchlist or {
            "timestamp": payload["timestamp"],
            "themes": [],
            "tickers": [],
            "overall_action": "NO SIGNAL",
        }
        previous = self.load_latest_youtube_snapshot()
        diff = self._build_youtube_diff(previous, payload)
        report = self._build_youtube_report(payload, diff, watchlist)
        watchlist_report = self._build_watchlist_report(watchlist)
        history_path = self._history_path(self.youtube_history_dir, payload["timestamp"])

        self._write_json(self.youtube_latest_snapshot_path, payload)
        self._write_json(history_path, payload)
        self._write_json(self.watchlist_latest_path, watchlist)
        self._write_text(self.youtube_latest_report_path, report)
        self._write_text(self.watchlist_report_path, watchlist_report)
        uploads = self.external_store.upload_files(
            [
                self.youtube_latest_snapshot_path,
                history_path,
                self.watchlist_latest_path,
                self.youtube_latest_report_path,
                self.watchlist_report_path,
            ]
        )

        return {
            "snapshot": payload,
            "watchlist": watchlist,
            "diff": diff,
            "history_path": history_path,
            "report_path": self.youtube_latest_report_path,
            "watchlist_report_path": self.watchlist_report_path,
            "uploads": uploads,
        }

    def load_latest_snapshot(self):
        return self._load_json(self.latest_snapshot_path)

    def load_latest_youtube_snapshot(self):
        return self._load_json(self.youtube_latest_snapshot_path)

    def load_latest_watchlist(self):
        return self._load_json(self.watchlist_latest_path)

    def notify_if_configured(self, result, webhook_url):
        if not self._is_valid_webhook_url(webhook_url):
            return False
        diff = result["diff"]
        interesting = (
            diff["new_news_count"] > 0
            or diff["new_youtube_count"] > 0
            or diff["decision_count"] > 0
            or len(result["snapshot"].get("ai_proposals", [])) > 0
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
            "watchlist": payload.get("watchlist", {}),
            "confirmed_watch_tickers": payload.get("confirmed_watch_tickers", []),
            "ai_proposals": payload.get("ai_proposals", []),
            "shortlisted_candidates": payload.get("shortlisted_candidates", []),
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
            item
            for item in current.get("news", [])
            if item["id"] not in previous_news_ids
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
            f"- AI proposals: {len(snapshot.get('ai_proposals', []))}",
            f"- Shortlisted candidates: {len(snapshot.get('shortlisted_candidates', []))}",
            f"- Decisions: {len(snapshot.get('decisions', []))}",
            f"- Confirmed watch tickers: {len(snapshot.get('confirmed_watch_tickers', []))}",
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

        lines.extend(["", "## AI Proposals"])
        if snapshot.get("ai_proposals"):
            for item in snapshot["ai_proposals"][:5]:
                lines.append(
                    f"- {item.get('ticker')}: {item.get('action')} ({item.get('confidence')}) {item.get('logic')}"
                )
        else:
            lines.append("- None")

        lines.extend(["", "## Shortlisted Candidates"])
        if snapshot.get("shortlisted_candidates"):
            for item in snapshot["shortlisted_candidates"][:5]:
                lines.append(
                    f"- {item.get('ticker')}: {item.get('action')} ({item.get('confidence')}) "
                    f"news_support={item.get('has_news_support')} change={item.get('change_rate')}"
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

    def _build_youtube_report(self, snapshot, diff, watchlist):
        lines = [
            f"# YouTube Patrol Report {snapshot['timestamp']}",
            "",
            "## Summary",
            f"- YouTube items: {len(snapshot.get('youtube', []))}",
            f"- New YouTube items since last run: {diff['new_youtube_count']}",
            f"- Watchlist action: {watchlist.get('overall_action', 'NO SIGNAL')}",
            "",
            "## Latest YouTube Items",
        ]
        latest_items = snapshot.get("youtube", [])[:5]
        if latest_items:
            for item in latest_items:
                sentiment = item.get("sentiment") or {}
                lines.append(
                    f"- [{item.get('channel')}] {item.get('title')} "
                    f"(score={sentiment.get('score')}, themes={','.join(item.get('themes', [])) or 'none'}, "
                    f"tickers={','.join(item.get('candidate_tickers', [])) or 'none'}, "
                    f"published={item.get('published')})"
                )
        else:
            lines.append("- None")
        lines.extend(["", "## New YouTube Since Last Run"])
        if diff["new_youtube"]:
            for item in diff["new_youtube"]:
                lines.append(f"- [{item.get('channel')}] {item.get('title')}")
        else:
            lines.append("- None")
        lines.extend(["", "## Watchlist Preview"])
        for item in watchlist.get("tickers", [])[:5]:
            lines.append(
                f"- {item.get('ticker')} action={item.get('action')} score={item.get('score')} "
                f"reasons={','.join(item.get('reasons', []))}"
            )
        if not watchlist.get("tickers"):
            lines.append("- None")
        lines.append("")
        return "\n".join(lines)

    def _build_watchlist_report(self, watchlist):
        source_summary = watchlist.get("source_summary") or {}
        lines = [
            f"# YouTube Watchlist {watchlist.get('timestamp')}",
            "",
            f"- Overall action: {watchlist.get('overall_action', 'NO SIGNAL')}",
            "",
            "## Source Summary",
            f"- Fixed channel items: {source_summary.get('fixed_channel_items', 0)}",
            f"- Search items: {source_summary.get('search_items', 0)}",
            f"- Fixed channels seen: {source_summary.get('fixed_channel_count', 0)}",
            f"- Search keywords seen: {source_summary.get('search_keyword_count', 0)}",
        ]
        top_fixed_channels = source_summary.get("top_fixed_channels") or []
        if top_fixed_channels:
            lines.append(
                "- Top fixed channels: "
                + ", ".join(
                    f"{item.get('name')}({item.get('count')})"
                    for item in top_fixed_channels[:3]
                )
            )
        top_search_keywords = source_summary.get("top_search_keywords") or []
        if top_search_keywords:
            lines.append(
                "- Top search keywords: "
                + ", ".join(
                    f"{item.get('keyword')}({item.get('count')})"
                    for item in top_search_keywords[:3]
                )
            )

        lines.extend([
            "",
            "## Top Themes",
        ])
        themes = watchlist.get("themes", [])
        if themes:
            for item in themes[:5]:
                lines.append(
                    f"- {item.get('name')} action={item.get('action')} score={item.get('score')} videos={item.get('video_count')}"
                )
        else:
            lines.append("- None")

        lines.extend(["", "## Top Tickers"])
        tickers = watchlist.get("tickers", [])
        if tickers:
            for item in tickers[:5]:
                lines.append(
                    f"- {item.get('ticker')} action={item.get('action')} score={item.get('score')} "
                    f"avg_sentiment={item.get('avg_sentiment')} reasons={','.join(item.get('reasons', []))}"
                )
        else:
            lines.append("- None")
        lines.append("")
        return "\n".join(lines)

    def _build_notification_text(self, result):
        diff = result["diff"]
        snapshot = result["snapshot"]
        action = self._main_action(snapshot, diff)
        lines = [
            f"Patrol update {snapshot.get('timestamp')}",
            f"Summary: news={diff['new_news_count']} youtube={diff['new_youtube_count']} decisions={diff['decision_count']}",
            f"Action: {action}",
        ]

        confirmed = snapshot.get("confirmed_watch_tickers", [])
        if confirmed:
            lines.append(f"Confirmed watch tickers: {', '.join(confirmed[:5])}")

        for item in snapshot.get("ai_proposals", [])[:3]:
            lines.append(
                "AI proposal: "
                f"{item.get('ticker')} {item.get('action')} confidence={item.get('confidence')}"
            )

        for item in diff["new_news"][:3]:
            lines.append(f"News: [{item.get('source')}] {item.get('title')}")

        for item in snapshot.get("decisions", [])[:3]:
            lines.append(
                "Decision: "
                f"{item.get('ticker')} {item.get('action')} "
                f"confidence={item.get('confidence')}"
            )

        lines.append(
            "Trading note: Confirm with price action and risk limits before any order."
        )
        return "\n".join(lines)

    def _build_youtube_notification_text(self, result):
        diff = result["diff"]
        snapshot = result["snapshot"]
        watchlist = result.get("watchlist") or {}
        source_summary = watchlist.get("source_summary") or {}
        top_item = diff["new_youtube"][0] if diff["new_youtube"] else None
        action = watchlist.get("overall_action") or self._youtube_action(top_item)
        themes = [item.get("name") for item in watchlist.get("themes", [])[:3]]
        if not themes:
            themes = self._infer_youtube_themes(top_item)
        lines = [
            f"YouTube patrol update {snapshot.get('timestamp')}",
            f"Summary: new_youtube={diff['new_youtube_count']}",
            f"Action: {action}",
        ]
        lines.append(
            "Sources: "
            f"fixed={source_summary.get('fixed_channel_items', 0)} "
            f"search={source_summary.get('search_items', 0)}"
        )
        top_fixed_channels = source_summary.get("top_fixed_channels") or []
        if top_fixed_channels:
            lines.append(
                "Top fixed channels: "
                + ", ".join(
                    f"{item.get('name')}({item.get('count')})"
                    for item in top_fixed_channels[:3]
                )
            )
        if themes:
            lines.append(f"Themes: {', '.join(themes)}")
        top_tickers = watchlist.get("tickers", [])[:3]
        if top_tickers:
            lines.append(
                "Candidates: "
                + ", ".join(
                    f"{item.get('ticker')}({item.get('action')})" for item in top_tickers
                )
            )
        for item in diff["new_youtube"][:3]:
            sentiment = item.get("sentiment") or {}
            lines.append(
                "Video: "
                f"[{item.get('channel')}] {item.get('title')} "
                f"score={sentiment.get('score')}"
            )
        lines.append(
            "Trading note: YouTube alone is not a buy signal. Confirm with price and news."
        )
        return "\n".join(lines)

    def _youtube_action(self, item):
        if not item:
            return "NO SIGNAL"
        sentiment = item.get("sentiment") or {}
        score = sentiment.get("score")
        try:
            score = float(score)
        except (TypeError, ValueError):
            return "NO SIGNAL"
        if score <= -0.4:
            return "AVOID"
        if score >= 0.6:
            return "WATCH"
        return "NO SIGNAL"

    def _main_action(self, snapshot, diff):
        decisions = snapshot.get("decisions", [])
        actions = {str(item.get("action", "")).upper() for item in decisions}
        if "BUY" in actions:
            return "BUY"
        if "SELL" in actions:
            return "SELL"
        if decisions:
            return "WATCH"
        if snapshot.get("ai_proposals"):
            return "WATCH"
        if diff["new_news_count"] > 0 or diff["new_youtube_count"] > 0:
            return "WATCH"
        return "NO SIGNAL"

    def _infer_youtube_themes(self, item):
        if not item:
            return []
        text = " ".join(
            str(part)
            for part in [
                item.get("title", ""),
                item.get("source", ""),
                (item.get("sentiment") or {}).get("reason", ""),
            ]
            if part
        ).lower()
        keyword_map = [
            ("日本株", ["日本株", "日経", "nikkei", "japan equities"]),
            ("半導体", ["半導体", "semiconductor"]),
            ("原油", ["原油", "wti", "oil", "crude"]),
            ("円安", ["円安", "ドル円", "usd/jpy", "yen"]),
            ("米国株", ["米国株", "nasdaq", "s&p", "dow"]),
            ("仮想通貨", ["仮想通貨", "bitcoin", "btc", "crypto"]),
        ]
        themes = []
        for theme, keywords in keyword_map:
            if any(keyword.lower() in text for keyword in keywords):
                themes.append(theme)
        return themes[:4]

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
        return (
            f"{item.get('source', '')}|{item.get('title', '')}|{item.get('published', '')}"
        )

    def _youtube_id(self, item):
        if item.get("video_id"):
            return item["video_id"]
        return (
            f"{item.get('channel', '')}|{item.get('title', '')}|{item.get('published', '')}"
        )
