from collections import defaultdict
from datetime import datetime


class WatchlistBuilder:
    def __init__(self, theme_ticker_map=None, rules=None):
        self.theme_ticker_map = theme_ticker_map or {}
        self.rules = rules or {}
        self.top_ticker_limit = int(self.rules.get("top_ticker_limit", 10))
        self.top_theme_limit = int(self.rules.get("top_theme_limit", 8))
        self.min_distinct_channels = int(self.rules.get("min_distinct_channels", 2))
        self.min_distinct_groups = int(self.rules.get("min_distinct_groups", 1))
        self.bullish_watch_threshold = float(
            self.rules.get("bullish_watch_threshold", 0.35)
        )
        self.bearish_avoid_threshold = float(
            self.rules.get("bearish_avoid_threshold", -0.35)
        )

    def build(self, youtube_items):
        theme_stats = defaultdict(
            lambda: {
                "score_total": 0.0,
                "weighted_score_total": 0.0,
                "bullish_mentions": 0,
                "bearish_mentions": 0,
                "video_count": 0,
                "groups": set(),
            }
        )
        ticker_stats = defaultdict(
            lambda: {
                "score_total": 0.0,
                "weighted_score_total": 0.0,
                "bullish_mentions": 0,
                "bearish_mentions": 0,
                "mention_count": 0,
                "channels": set(),
                "groups": set(),
                "reasons": set(),
            }
        )

        for item in youtube_items:
            sentiment = item.get("sentiment") or {}
            score = self._safe_float(sentiment.get("score"))
            weight = self._safe_float(item.get("channel_weight"), default=1.0)
            themes = item.get("themes") or []
            tickers = item.get("candidate_tickers") or []
            channel = item.get("channel")
            group = item.get("channel_group") or "search"

            for theme in themes:
                stats = theme_stats[theme]
                stats["score_total"] += score
                stats["weighted_score_total"] += score * weight
                stats["video_count"] += 1
                stats["groups"].add(group)
                if score >= 0.25:
                    stats["bullish_mentions"] += 1
                elif score <= -0.25:
                    stats["bearish_mentions"] += 1

            for ticker in tickers:
                stats = ticker_stats[ticker]
                stats["score_total"] += score
                stats["weighted_score_total"] += score * weight
                stats["mention_count"] += 1
                if score >= 0.25:
                    stats["bullish_mentions"] += 1
                elif score <= -0.25:
                    stats["bearish_mentions"] += 1
                if channel:
                    stats["channels"].add(channel)
                stats["groups"].add(group)
                for theme in themes:
                    stats["reasons"].add(f"theme:{theme}")
                source = item.get("source")
                if source:
                    stats["reasons"].add(source)
                stats["reasons"].add(f"group:{group}")

        top_themes = self._build_theme_rows(theme_stats)
        top_tickers = self._build_ticker_rows(ticker_stats)

        return {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "themes": top_themes[: self.top_theme_limit],
            "tickers": top_tickers[: self.top_ticker_limit],
            "overall_action": self._overall_action(top_tickers),
        }

    def _build_theme_rows(self, theme_stats):
        rows = []
        for theme, stats in theme_stats.items():
            avg_score = stats["score_total"] / max(stats["video_count"], 1)
            weighted_avg_score = stats["weighted_score_total"] / max(
                stats["video_count"], 1
            )
            action = self._score_action(weighted_avg_score)
            rows.append(
                {
                    "name": theme,
                    "score": round(avg_score, 2),
                    "weighted_score": round(weighted_avg_score, 2),
                    "video_count": stats["video_count"],
                    "group_count": len(stats["groups"]),
                    "bullish_mentions": stats["bullish_mentions"],
                    "bearish_mentions": stats["bearish_mentions"],
                    "action": action,
                }
            )
        rows.sort(
            key=lambda item: (abs(item["weighted_score"]), item["video_count"]),
            reverse=True,
        )
        return rows

    def _build_ticker_rows(self, ticker_stats):
        rows = []
        for ticker, stats in ticker_stats.items():
            avg_score = stats["score_total"] / max(stats["mention_count"], 1)
            weighted_avg_score = stats["weighted_score_total"] / max(
                stats["mention_count"], 1
            )
            distinct_channels = len(stats["channels"])
            distinct_groups = len(stats["groups"])
            bullish_ratio = stats["bullish_mentions"] / max(stats["mention_count"], 1)
            bearish_ratio = stats["bearish_mentions"] / max(stats["mention_count"], 1)
            watch_score = round(
                (stats["mention_count"] * 1.0)
                + (distinct_channels * 0.8)
                + (distinct_groups * 1.2)
                + (bullish_ratio * 0.8)
                - (bearish_ratio * 0.8)
                + weighted_avg_score,
                2,
            )
            rows.append(
                {
                    "ticker": ticker,
                    "score": watch_score,
                    "avg_sentiment": round(avg_score, 2),
                    "weighted_sentiment": round(weighted_avg_score, 2),
                    "mention_count": stats["mention_count"],
                    "channel_count": distinct_channels,
                    "group_count": distinct_groups,
                    "action": self._ticker_action(
                        weighted_avg_score, distinct_channels, distinct_groups
                    ),
                    "reasons": sorted(stats["reasons"])[:6],
                }
            )
        rows.sort(
            key=lambda item: (item["score"], abs(item["weighted_sentiment"])),
            reverse=True,
        )
        return rows

    def _score_action(self, score):
        if score <= self.bearish_avoid_threshold:
            return "AVOID"
        if score >= self.bullish_watch_threshold:
            return "WATCH"
        return "NO SIGNAL"

    def _ticker_action(self, score, distinct_channels, distinct_groups):
        if score <= self.bearish_avoid_threshold:
            return "AVOID"
        if (
            score >= self.bullish_watch_threshold
            and distinct_channels >= self.min_distinct_channels
            and distinct_groups >= self.min_distinct_groups
        ):
            return "WATCH"
        return "NO SIGNAL"

    def _overall_action(self, ticker_rows):
        if not ticker_rows:
            return "NO SIGNAL"
        actions = {item.get("action") for item in ticker_rows[:5]}
        if "WATCH" in actions:
            return "WATCH"
        if "AVOID" in actions:
            return "AVOID"
        return "NO SIGNAL"

    def _safe_float(self, value, default=0.0):
        try:
            return float(value)
        except (TypeError, ValueError):
            return default
