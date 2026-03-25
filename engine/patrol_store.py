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
                    "source_list": item.get("source_list", []),
                    "published": item.get("published"),
                    "channel_group": item.get("channel_group"),
                    "group_list": item.get("group_list", []),
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
        previous_watchlist = self.load_latest_watchlist()
        diff = self._build_youtube_diff(previous, payload, previous_watchlist, watchlist)
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
            or diff.get("watchlist_status_changed")
            or diff.get("top_watchlist_changed")
            or diff.get("runtime_config_changed")
            or diff.get("ai_runtime_changed")
            or diff.get("confirmed_watch_changed")
            or diff.get("top_ai_proposals_changed")
            or diff.get("top_shortlisted_changed")
            or diff.get("top_decisions_changed")
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
        if (
            diff["new_youtube_count"] <= 0
            and not diff.get("watchlist_action_changed")
            and not diff.get("top_tickers_changed")
        ):
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
                    "source_list": item.get("source_list", []),
                    "published": item.get("published"),
                    "channel_group": item.get("channel_group"),
                    "group_list": item.get("group_list", []),
                    "sentiment": item.get("sentiment"),
                }
                for item in payload.get("youtube", [])
            ],
            "watchlist": payload.get("watchlist", {}),
            "watchlist_status": payload.get("watchlist_status", "unknown"),
            "runtime_config": payload.get("runtime_config", {}),
            "ai_runtime": payload.get("ai_runtime", {}),
            "confirmed_watch_tickers": payload.get("confirmed_watch_tickers", []),
            "ai_proposals": payload.get("ai_proposals", []),
            "shortlisted_candidates": payload.get("shortlisted_candidates", []),
            "paper_trade_summary": payload.get("paper_trade_summary", {}),
            "paper_trade_events": payload.get("paper_trade_events", []),
            "decisions": payload.get("decisions", []),
            "portfolio": payload.get("portfolio", {}),
        }

    def _build_diff(self, previous, current):
        previous_news_ids = set()
        previous_youtube_ids = set()
        previous_confirmed = []
        previous_ai = []
        previous_shortlisted = []
        previous_decisions = []
        previous_watchlist_status = "unknown"
        previous_watchlist_top = []
        previous_runtime_config = {}
        previous_ai_mode = "unknown"
        previous_ai_models = {}
        previous_ai_cooldown = None
        previous_ai_request_config = {}
        if previous:
            previous_news_ids = {item["id"] for item in previous.get("news", [])}
            previous_youtube_ids = {item["id"] for item in previous.get("youtube", [])}
            previous_watchlist_status = previous.get("watchlist_status", "unknown")
            previous_watchlist_top = [
                f"{item.get('ticker')}:{item.get('action')}"
                for item in (previous.get("watchlist") or {}).get("tickers", [])[:3]
                if item.get("ticker") and item.get("action")
            ]
            previous_runtime_config = previous.get("runtime_config") or {}
            previous_ai_runtime = previous.get("ai_runtime") or {}
            previous_ai_mode = "live" if previous_ai_runtime.get("api_enabled") else "mock"
            previous_ai_models = {
                "sentiment_model": previous_ai_runtime.get("sentiment_model"),
                "proposal_model": previous_ai_runtime.get("proposal_model"),
                "council_model": previous_ai_runtime.get("council_model"),
            }
            previous_ai_cooldown = previous_ai_runtime.get("cooldown_reason")
            previous_ai_request_config = {
                "request_timeout": previous_ai_runtime.get("request_timeout"),
                "max_retries": previous_ai_runtime.get("max_retries"),
                "retry_backoff_seconds": previous_ai_runtime.get("retry_backoff_seconds"),
                "cooldown_seconds": previous_ai_runtime.get("cooldown_seconds"),
            }
            previous_confirmed = previous.get("confirmed_watch_tickers", [])[:5]
            previous_ai = [
                item.get("ticker")
                for item in previous.get("ai_proposals", [])[:3]
                if item.get("ticker")
            ]
            previous_shortlisted = [
                f"{item.get('ticker')}:{item.get('action')}"
                for item in previous.get("shortlisted_candidates", [])[:3]
                if item.get("ticker") and item.get("action")
            ]
            previous_decisions = [
                f"{item.get('ticker')}:{item.get('action')}"
                for item in previous.get("decisions", [])[:3]
                if item.get("ticker") and item.get("action")
            ]

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
        current_confirmed = current.get("confirmed_watch_tickers", [])[:5]
        current_ai = [
            item.get("ticker")
            for item in current.get("ai_proposals", [])[:3]
            if item.get("ticker")
        ]
        current_shortlisted = [
            f"{item.get('ticker')}:{item.get('action')}"
            for item in current.get("shortlisted_candidates", [])[:3]
            if item.get("ticker") and item.get("action")
        ]
        current_decisions = [
            f"{item.get('ticker')}:{item.get('action')}"
            for item in current.get("decisions", [])[:3]
            if item.get("ticker") and item.get("action")
        ]
        current_watchlist_status = current.get("watchlist_status", "unknown")
        current_watchlist_top = [
            f"{item.get('ticker')}:{item.get('action')}"
            for item in (current.get("watchlist") or {}).get("tickers", [])[:3]
            if item.get("ticker") and item.get("action")
        ]
        current_runtime_config = current.get("runtime_config") or {}
        current_ai_runtime = current.get("ai_runtime") or {}
        current_ai_mode = "live" if current_ai_runtime.get("api_enabled") else "mock"
        current_ai_models = {
            "sentiment_model": current_ai_runtime.get("sentiment_model"),
            "proposal_model": current_ai_runtime.get("proposal_model"),
            "council_model": current_ai_runtime.get("council_model"),
        }
        current_ai_cooldown = current_ai_runtime.get("cooldown_reason")
        current_ai_request_config = {
            "request_timeout": current_ai_runtime.get("request_timeout"),
            "max_retries": current_ai_runtime.get("max_retries"),
            "retry_backoff_seconds": current_ai_runtime.get("retry_backoff_seconds"),
            "cooldown_seconds": current_ai_runtime.get("cooldown_seconds"),
        }

        return {
            "new_news_count": len(new_news),
            "new_youtube_count": len(new_youtube),
            "decision_count": len(current.get("decisions", [])),
            "new_news": new_news[:5],
            "new_youtube": new_youtube[:5],
            "watchlist_status_changed": previous_watchlist_status != current_watchlist_status,
            "previous_watchlist_status": previous_watchlist_status,
            "current_watchlist_status": current_watchlist_status,
            "top_watchlist_changed": previous_watchlist_top != current_watchlist_top,
            "previous_top_watchlist": previous_watchlist_top,
            "current_top_watchlist": current_watchlist_top,
            "runtime_config_changed": previous_runtime_config != current_runtime_config,
            "previous_runtime_config": previous_runtime_config,
            "current_runtime_config": current_runtime_config,
            "ai_runtime_changed": (
                previous_ai_mode != current_ai_mode
                or previous_ai_models != current_ai_models
                or previous_ai_cooldown != current_ai_cooldown
                or previous_ai_request_config != current_ai_request_config
            ),
            "previous_ai_mode": previous_ai_mode,
            "current_ai_mode": current_ai_mode,
            "previous_ai_models": previous_ai_models,
            "current_ai_models": current_ai_models,
            "previous_ai_cooldown": previous_ai_cooldown,
            "current_ai_cooldown": current_ai_cooldown,
            "previous_ai_request_config": previous_ai_request_config,
            "current_ai_request_config": current_ai_request_config,
            "confirmed_watch_changed": previous_confirmed != current_confirmed,
            "previous_confirmed_watch_tickers": previous_confirmed,
            "current_confirmed_watch_tickers": current_confirmed,
            "top_ai_proposals_changed": previous_ai != current_ai,
            "previous_top_ai_proposals": previous_ai,
            "current_top_ai_proposals": current_ai,
            "top_shortlisted_changed": previous_shortlisted != current_shortlisted,
            "previous_top_shortlisted": previous_shortlisted,
            "current_top_shortlisted": current_shortlisted,
            "top_decisions_changed": previous_decisions != current_decisions,
            "previous_top_decisions": previous_decisions,
            "current_top_decisions": current_decisions,
        }

    def _build_youtube_diff(self, previous, current, previous_watchlist=None, current_watchlist=None):
        previous_ids = set()
        if previous:
            previous_ids = {item["id"] for item in previous.get("youtube", [])}
        new_youtube = [
            item for item in current.get("youtube", []) if item["id"] not in previous_ids
        ]
        previous_action = (previous_watchlist or {}).get("overall_action", "NO SIGNAL")
        current_action = (current_watchlist or {}).get("overall_action", "NO SIGNAL")
        previous_tickers = [
            item.get("ticker")
            for item in (previous_watchlist or {}).get("tickers", [])[:3]
            if item.get("ticker")
        ]
        current_tickers = [
            item.get("ticker")
            for item in (current_watchlist or {}).get("tickers", [])[:3]
            if item.get("ticker")
        ]
        return {
            "new_youtube_count": len(new_youtube),
            "new_youtube": new_youtube[:5],
            "watchlist_action_changed": previous_action != current_action,
            "previous_watchlist_action": previous_action,
            "current_watchlist_action": current_action,
            "top_tickers_changed": previous_tickers != current_tickers,
            "previous_top_tickers": previous_tickers,
            "current_top_tickers": current_tickers,
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
            f"- Paper trade events: {len(snapshot.get('paper_trade_events', []))}",
            f"- Decisions: {len(snapshot.get('decisions', []))}",
            f"- Watchlist tickers: {len((snapshot.get('watchlist') or {}).get('tickers', []))}",
            f"- Watchlist action: {(snapshot.get('watchlist') or {}).get('overall_action', 'NO SIGNAL')}",
            f"- Watchlist timestamp: {(snapshot.get('watchlist') or {}).get('timestamp', 'None')}",
            f"- Confirmed watch tickers: {len(snapshot.get('confirmed_watch_tickers', []))}",
            f"- Watchlist status: {snapshot.get('watchlist_status', 'unknown')}",
            f"- AI mode: {'live' if (snapshot.get('ai_runtime') or {}).get('api_enabled') else 'mock'}",
            f"- AI sentiment requests: {(snapshot.get('ai_runtime') or {}).get('sentiment_requests_used', 0)}/"
            f"{(snapshot.get('ai_runtime') or {}).get('sentiment_request_limit', 0)}",
            f"- AI cooldown active: {'yes' if (snapshot.get('ai_runtime') or {}).get('cooldown_reason') else 'no'}",
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

        lines.extend(["", "## Runtime Config"])
        runtime_config = snapshot.get("runtime_config") or {}
        if runtime_config:
            lines.append(
                f"- youtube_max_videos={runtime_config.get('youtube_max_videos')} "
                f"youtube_max_items={runtime_config.get('youtube_max_items')} "
                f"youtube_recent_hours={runtime_config.get('youtube_recent_hours')}"
            )
            lines.append(
                f"- use_transcripts={runtime_config.get('use_transcripts')} "
                f"parallel_workers={runtime_config.get('parallel_workers')} "
                f"enable_youtube_analysis={runtime_config.get('enable_youtube_analysis')}"
            )
            lines.append(
                f"- max_watchlist_age_hours={runtime_config.get('max_watchlist_age_hours')} "
                f"buy_requires_price_confirmation={runtime_config.get('buy_requires_price_confirmation')} "
                f"min_price_confirmation_change_pct={runtime_config.get('min_price_confirmation_change_pct')}"
            )
            lines.append(
                f"- ai_proposal_min_confidence={runtime_config.get('ai_proposal_min_confidence')}"
            )
        else:
            lines.append("- None")

        lines.extend(["", "## Watchlist Preview"])
        watchlist = snapshot.get("watchlist") or {}
        if watchlist:
            lines.append(
                f"- Overall action: {watchlist.get('overall_action', 'NO SIGNAL')}"
            )
            tickers = watchlist.get("tickers", [])
            if tickers:
                for item in tickers[:5]:
                    lines.append(
                        f"- {item.get('ticker')}: {item.get('action')} "
                        f"score={item.get('score')} reasons={','.join(item.get('reasons', [])) or 'none'}"
                    )
            else:
                lines.append("- None")
        else:
            lines.append("- None")

        lines.extend(["", "## Confirmed Watch"])
        confirmed_watch = snapshot.get("confirmed_watch_tickers", [])
        if confirmed_watch:
            for ticker in confirmed_watch[:5]:
                lines.append(f"- {ticker}")
        else:
            lines.append("- None")

        lines.extend(["", "## AI Proposals"])
        ai_runtime = snapshot.get("ai_runtime") or {}
        if ai_runtime:
            lines.append(
                "- Runtime: "
                f"sentiment={ai_runtime.get('sentiment_model')} "
                f"proposal={ai_runtime.get('proposal_model')} "
                f"council={ai_runtime.get('council_model')} "
                f"requests={ai_runtime.get('sentiment_requests_used', 0)}/"
                f"{ai_runtime.get('sentiment_request_limit', 0)}"
            )
            lines.append(
                "- AI request config: "
                f"timeout={ai_runtime.get('request_timeout')} "
                f"retries={ai_runtime.get('max_retries')} "
                f"backoff={ai_runtime.get('retry_backoff_seconds')} "
                f"cooldown={ai_runtime.get('cooldown_seconds')}"
            )
            if ai_runtime.get("cooldown_reason"):
                lines.append(f"- AI cooldown: {ai_runtime.get('cooldown_reason')}")
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

        if (
            diff.get("watchlist_status_changed")
            or diff.get("top_watchlist_changed")
            or diff.get("runtime_config_changed")
            or diff.get("ai_runtime_changed")
            or diff.get("confirmed_watch_changed")
            or diff.get("top_ai_proposals_changed")
            or diff.get("top_shortlisted_changed")
            or diff.get("top_decisions_changed")
        ):
            lines.extend(["", "## Stage Changes"])
            if diff.get("watchlist_status_changed"):
                lines.append(
                    "- Watchlist status: "
                    f"{diff.get('previous_watchlist_status', 'unknown')}"
                    " -> "
                    f"{diff.get('current_watchlist_status', 'unknown')}"
                )
            if diff.get("top_watchlist_changed"):
                lines.append(
                    "- Watchlist top: "
                    f"{', '.join(diff.get('previous_top_watchlist', [])) or 'None'}"
                    " -> "
                    f"{', '.join(diff.get('current_top_watchlist', [])) or 'None'}"
                )
            if diff.get("runtime_config_changed"):
                before_config = diff.get("previous_runtime_config", {})
                after_config = diff.get("current_runtime_config", {})
                lines.append(
                    "- Runtime config: "
                    f"youtube_max_videos={before_config.get('youtube_max_videos')}->{after_config.get('youtube_max_videos')} "
                    f"youtube_max_items={before_config.get('youtube_max_items')}->{after_config.get('youtube_max_items')} "
                    f"max_watchlist_age_hours={before_config.get('max_watchlist_age_hours')}->{after_config.get('max_watchlist_age_hours')}"
                )
            if diff.get("ai_runtime_changed"):
                before_mode = diff.get("previous_ai_mode", "unknown")
                after_mode = diff.get("current_ai_mode", "unknown")
                before_models = diff.get("previous_ai_models", {})
                after_models = diff.get("current_ai_models", {})
                lines.append(
                    "- AI runtime: "
                    f"{before_mode}({before_models.get('sentiment_model')},{before_models.get('proposal_model')},{before_models.get('council_model')})"
                    " -> "
                    f"{after_mode}({after_models.get('sentiment_model')},{after_models.get('proposal_model')},{after_models.get('council_model')})"
                )
                if diff.get("previous_ai_cooldown") != diff.get("current_ai_cooldown"):
                    lines.append(
                        "- AI cooldown: "
                        f"{diff.get('previous_ai_cooldown') or 'None'}"
                        " -> "
                        f"{diff.get('current_ai_cooldown') or 'None'}"
                    )
                if diff.get("previous_ai_request_config") != diff.get("current_ai_request_config"):
                    before_request = diff.get("previous_ai_request_config", {})
                    after_request = diff.get("current_ai_request_config", {})
                    lines.append(
                        "- AI request config: "
                        f"timeout={before_request.get('request_timeout')}->{after_request.get('request_timeout')} "
                        f"retries={before_request.get('max_retries')}->{after_request.get('max_retries')} "
                        f"backoff={before_request.get('retry_backoff_seconds')}->{after_request.get('retry_backoff_seconds')} "
                        f"cooldown={before_request.get('cooldown_seconds')}->{after_request.get('cooldown_seconds')}"
                    )
            if diff.get("confirmed_watch_changed"):
                lines.append(
                    "- Confirmed watch: "
                    f"{', '.join(diff.get('previous_confirmed_watch_tickers', [])) or 'None'}"
                    " -> "
                    f"{', '.join(diff.get('current_confirmed_watch_tickers', [])) or 'None'}"
                )
            if diff.get("top_ai_proposals_changed"):
                lines.append(
                    "- AI proposals: "
                    f"{', '.join(diff.get('previous_top_ai_proposals', [])) or 'None'}"
                    " -> "
                    f"{', '.join(diff.get('current_top_ai_proposals', [])) or 'None'}"
                )
            if diff.get("top_shortlisted_changed"):
                lines.append(
                    "- Shortlisted: "
                    f"{', '.join(diff.get('previous_top_shortlisted', [])) or 'None'}"
                    " -> "
                    f"{', '.join(diff.get('current_top_shortlisted', [])) or 'None'}"
                )
            if diff.get("top_decisions_changed"):
                lines.append(
                    "- Final decisions: "
                    f"{', '.join(diff.get('previous_top_decisions', [])) or 'None'}"
                    " -> "
                    f"{', '.join(diff.get('current_top_decisions', [])) or 'None'}"
                )

        lines.extend(["", "## Paper Trade Summary"])
        paper_summary = snapshot.get("paper_trade_summary") or {}
        if paper_summary:
            lines.append(f"- Open positions: {paper_summary.get('open_positions', 0)}")
            lines.append(f"- Closed trades: {paper_summary.get('closed_trades', 0)}")
            lines.append(f"- Win rate: {paper_summary.get('win_rate', 0)}%")
            lines.append(f"- Realized PnL: {paper_summary.get('realized_pnl', 0)}")
            lines.append(f"- Unrealized PnL: {paper_summary.get('unrealized_pnl', 0)}")
            lines.append(f"- Total PnL: {paper_summary.get('total_pnl', 0)}")
            lines.append(
                f"- Average holding days: {paper_summary.get('average_holding_days', 0)}"
            )
            recent_actions = paper_summary.get("recent_signal_actions", [])
            if recent_actions:
                lines.append(f"- Recent signal actions: {', '.join(recent_actions[:5])}")
            recent_proposals = paper_summary.get("recent_proposal_actions", [])
            if recent_proposals:
                lines.append(f"- Recent proposal actions: {', '.join(recent_proposals[:5])}")
            recent_finals = paper_summary.get("recent_final_actions", [])
            if recent_finals:
                lines.append(f"- Recent final actions: {', '.join(recent_finals[:5])}")
            positions = paper_summary.get("positions", [])
            if positions:
                lines.append("- Open position preview:")
                for item in positions[:3]:
                    lines.append(
                        f"  - {item.get('ticker')}: entry={item.get('entry_price')} "
                        f"current={item.get('current_price')} pnl={item.get('unrealized_pnl')} "
                        f"holding_days={item.get('holding_days')}"
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
            f"- Watchlist action changed: {diff.get('watchlist_action_changed', False)}",
            f"- Top tickers changed: {diff.get('top_tickers_changed', False)}",
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
                top_fixed = item.get("top_fixed_channels") or []
                top_fixed_text = (
                    ", ".join(
                        f"{entry.get('name')}({entry.get('count')})" for entry in top_fixed[:2]
                    )
                    if top_fixed
                    else "none"
                )
                lines.append(
                    f"- {item.get('name')} action={item.get('action')} score={item.get('score')} "
                    f"videos={item.get('video_count')} fixed={item.get('fixed_source_count', 0)} "
                    f"search={item.get('search_source_count', 0)} fixed_channels={top_fixed_text}"
                )
        else:
            lines.append("- None")

        lines.extend(["", "## Top Tickers"])
        tickers = watchlist.get("tickers", [])
        if tickers:
            for item in tickers[:5]:
                top_fixed = item.get("top_fixed_channels") or []
                top_fixed_text = (
                    ", ".join(
                        f"{entry.get('name')}({entry.get('count')})" for entry in top_fixed[:2]
                    )
                    if top_fixed
                    else "none"
                )
                lines.append(
                    f"- {item.get('ticker')} action={item.get('action')} score={item.get('score')} "
                    f"avg_sentiment={item.get('avg_sentiment')} fixed={item.get('fixed_source_count', 0)} "
                    f"search={item.get('search_source_count', 0)} fixed_channels={top_fixed_text} "
                    f"reasons={','.join(item.get('reasons', []))}"
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
            f"巡回アップデート {snapshot.get('timestamp')}",
            (
                "概要: "
                f"ニュース新着={diff['new_news_count']}件 "
                f"YouTube新着={diff['new_youtube_count']}件 "
                f"判断={diff['decision_count']}件"
            ),
            f"行動: {self._action_label(action)}",
        ]
        ai_runtime = snapshot.get("ai_runtime") or {}
        if ai_runtime:
            mode = "live" if ai_runtime.get("api_enabled") else "mock"
            lines.append(
                "AI状態: "
                f"{mode} "
                f"sentiment={ai_runtime.get('sentiment_model')} "
                f"proposal={ai_runtime.get('proposal_model')} "
                f"council={ai_runtime.get('council_model')}"
            )
            if ai_runtime.get("cooldown_reason"):
                lines.append(f"AI制限状態: {ai_runtime.get('cooldown_reason')}")

        confirmed = snapshot.get("confirmed_watch_tickers", [])
        watchlist_status = snapshot.get("watchlist_status", "unknown")
        if watchlist_status != "fresh":
            lines.append(f"watchlist状態: {watchlist_status}")
        if diff.get("watchlist_status_changed"):
            before = diff.get("previous_watchlist_status", "unknown")
            after = diff.get("current_watchlist_status", "unknown")
            lines.append(f"watchlist状態変化: {before} → {after}")
        if diff.get("top_watchlist_changed"):
            before = ", ".join(diff.get("previous_top_watchlist", [])) or "なし"
            after = ", ".join(diff.get("current_top_watchlist", [])) or "なし"
            lines.append(f"watchlist候補変化: {before} → {after}")
        if diff.get("runtime_config_changed"):
            before_config = diff.get("previous_runtime_config", {})
            after_config = diff.get("current_runtime_config", {})
            lines.append(
                "設定変化: "
                f"videos {before_config.get('youtube_max_videos')}→{after_config.get('youtube_max_videos')}, "
                f"items {before_config.get('youtube_max_items')}→{after_config.get('youtube_max_items')}, "
                f"watchlist_age {before_config.get('max_watchlist_age_hours')}→{after_config.get('max_watchlist_age_hours')}"
            )
        if diff.get("ai_runtime_changed"):
            before_mode = diff.get("previous_ai_mode", "unknown")
            after_mode = diff.get("current_ai_mode", "unknown")
            before_models = diff.get("previous_ai_models", {})
            after_models = diff.get("current_ai_models", {})
            lines.append(
                "AI状態変化: "
                f"{before_mode}({before_models.get('sentiment_model')},{before_models.get('proposal_model')},{before_models.get('council_model')}) "
                "→ "
                f"{after_mode}({after_models.get('sentiment_model')},{after_models.get('proposal_model')},{after_models.get('council_model')})"
            )
            if diff.get("previous_ai_cooldown") != diff.get("current_ai_cooldown"):
                before_cooldown = diff.get("previous_ai_cooldown") or "なし"
                after_cooldown = diff.get("current_ai_cooldown") or "なし"
                lines.append(f"AI制限状態変化: {before_cooldown} → {after_cooldown}")
            if diff.get("previous_ai_request_config") != diff.get("current_ai_request_config"):
                before_request = diff.get("previous_ai_request_config", {})
                after_request = diff.get("current_ai_request_config", {})
                lines.append(
                    "AIリクエスト設定変化: "
                    f"timeout {before_request.get('request_timeout')}→{after_request.get('request_timeout')}, "
                    f"retries {before_request.get('max_retries')}→{after_request.get('max_retries')}, "
                    f"backoff {before_request.get('retry_backoff_seconds')}→{after_request.get('retry_backoff_seconds')}, "
                    f"cooldown {before_request.get('cooldown_seconds')}→{after_request.get('cooldown_seconds')}"
                )
        if confirmed:
            lines.append(f"価格確認済み監視銘柄: {', '.join(confirmed[:5])}")
        if diff.get("confirmed_watch_changed"):
            before = ", ".join(diff.get("previous_confirmed_watch_tickers", [])) or "なし"
            after = ", ".join(diff.get("current_confirmed_watch_tickers", [])) or "なし"
            lines.append(f"確認済み監視変化: {before} → {after}")

        paper_summary = snapshot.get("paper_trade_summary") or {}
        if paper_summary:
            lines.append(
                "紙上売買: "
                f"決済={paper_summary.get('closed_trades', 0)} "
                f"保有={paper_summary.get('open_positions', 0)} "
                f"合計損益={paper_summary.get('total_pnl', 0)}"
            )
            lines.append(
                "紙上売買詳細: "
                f"平均保有日数={paper_summary.get('average_holding_days', 0)} "
                f"最近アクション={', '.join((paper_summary.get('recent_signal_actions') or [])[:3]) or 'なし'}"
            )
            lines.append(
                "段階別シグナル: "
                f"proposal={', '.join((paper_summary.get('recent_proposal_actions') or [])[:3]) or 'なし'} "
                f"final={', '.join((paper_summary.get('recent_final_actions') or [])[:3]) or 'なし'}"
            )
            lines.append(
                "紙上売買連続記録: "
                f"連勝={paper_summary.get('best_win_streak', 0)} "
                f"連敗={paper_summary.get('best_loss_streak', 0)}"
            )
            ticker_pnl = paper_summary.get("ticker_pnl") or []
            if ticker_pnl:
                lines.append(
                    "銘柄別損益: "
                    + ", ".join(
                        f"{item.get('ticker')}={item.get('realized_pnl')}"
                        for item in ticker_pnl[:3]
                    )
                )

        if diff.get("top_ai_proposals_changed"):
            before = ", ".join(diff.get("previous_top_ai_proposals", [])) or "なし"
            after = ", ".join(diff.get("current_top_ai_proposals", [])) or "なし"
            lines.append(f"AI提案変化: {before} → {after}")
        if diff.get("top_shortlisted_changed"):
            before = ", ".join(diff.get("previous_top_shortlisted", [])) or "なし"
            after = ", ".join(diff.get("current_top_shortlisted", [])) or "なし"
            lines.append(f"候補絞り込み変化: {before} → {after}")
        if diff.get("top_decisions_changed"):
            before = ", ".join(diff.get("previous_top_decisions", [])) or "なし"
            after = ", ".join(diff.get("current_top_decisions", [])) or "なし"
            lines.append(f"最終判断変化: {before} → {after}")

        for item in snapshot.get("ai_proposals", [])[:3]:
            lines.append(
                "AI提案: "
                f"{item.get('ticker')} {self._action_label(item.get('action'))} "
                f"信頼度={item.get('confidence')}"
            )

        for item in diff["new_news"][:3]:
            lines.append(f"ニュース: [{item.get('source')}] {item.get('title')}")

        for item in snapshot.get("decisions", [])[:3]:
            lines.append(
                "判断: "
                f"{item.get('ticker')} {self._action_label(item.get('action'))} "
                f"信頼度={item.get('confidence')}"
            )

        lines.append(
            "補足: 注文前に値動きとリスク上限を必ず確認してください。"
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
            f"YouTube巡回アップデート {snapshot.get('timestamp')}",
            f"概要: YouTube新着={diff['new_youtube_count']}件",
            f"行動: {self._action_label(action)}",
        ]
        if diff.get("watchlist_action_changed"):
            lines.append(
                "watchlist変化: "
                f"{self._action_label(diff.get('previous_watchlist_action'))} → "
                f"{self._action_label(diff.get('current_watchlist_action'))}"
            )
        if diff.get("top_tickers_changed"):
            before = ", ".join(diff.get("previous_top_tickers", [])) or "なし"
            after = ", ".join(diff.get("current_top_tickers", [])) or "なし"
            lines.append(f"上位候補変化: {before} → {after}")
        lines.append(
            "取得元: "
            f"固定チャンネル={source_summary.get('fixed_channel_items', 0)}件 "
            f"検索={source_summary.get('search_items', 0)}件"
        )
        top_fixed_channels = source_summary.get("top_fixed_channels") or []
        if top_fixed_channels:
            lines.append(
                "上位固定チャンネル: "
                + ", ".join(
                    f"{item.get('name')}({item.get('count')})"
                    for item in top_fixed_channels[:3]
                )
            )
        if themes:
            lines.append(f"テーマ: {', '.join(themes)}")
        top_tickers = watchlist.get("tickers", [])[:3]
        if top_tickers:
            lines.append(
                "候補銘柄: "
                + ", ".join(
                    f"{item.get('ticker')}({self._action_label(item.get('action'))}"
                    f"/固定{item.get('fixed_source_count', 0)}"
                    f"/検索{item.get('search_source_count', 0)})"
                    for item in top_tickers
                )
            )
        for item in diff["new_youtube"][:3]:
            sentiment = item.get("sentiment") or {}
            lines.append(
                "動画: "
                f"[{item.get('channel')}] {item.get('title')} "
                f"score={sentiment.get('score')}"
            )
        lines.append(
            "補足: YouTube 単独では買いシグナルにしません。価格とニュースで確認してください。"
        )
        return "\n".join(lines)

    def _action_label(self, action):
        mapping = {
            "BUY": "買い",
            "SELL": "売り",
            "WATCH": "監視",
            "AVOID": "見送り",
            "NO SIGNAL": "シグナルなし",
        }
        key = str(action or "").upper()
        return mapping.get(key, str(action))

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
        if actions and actions.issubset({"AVOID", "NO SIGNAL", "WAIT"}):
            return "AVOID"
        if decisions:
            return "WATCH"
        proposal_actions = {
            str(item.get("action", "")).upper()
            for item in snapshot.get("ai_proposals", [])
        }
        if proposal_actions and proposal_actions.issubset({"AVOID", "NO SIGNAL"}):
            return "AVOID"
        if snapshot.get("ai_proposals"):
            return "WATCH"
        if snapshot.get("confirmed_watch_tickers"):
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
