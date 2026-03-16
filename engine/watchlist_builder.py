from collections import defaultdict
from datetime import datetime


class WatchlistBuilder:
    def __init__(self, theme_ticker_map=None):
        self.theme_ticker_map = theme_ticker_map or {}

    def build(self, youtube_items):
        theme_stats = defaultdict(
            lambda: {"score_total": 0.0, "bullish_mentions": 0, "bearish_mentions": 0, "video_count": 0}
        )
        ticker_stats = defaultdict(
            lambda: {
                "score_total": 0.0,
                "bullish_mentions": 0,
                "bearish_mentions": 0,
                "mention_count": 0,
                "channels": set(),
                "reasons": set(),
            }
        )

        for item in youtube_items:
            sentiment = item.get("sentiment") or {}
            score = self._safe_float(sentiment.get("score"))
            themes = item.get("themes") or []
            tickers = item.get("candidate_tickers") or []
            channel = item.get("channel")

            for theme in themes:
                stats = theme_stats[theme]
                stats["score_total"] += score
                stats["video_count"] += 1
                if score >= 0.25:
                    stats["bullish_mentions"] += 1
                elif score <= -0.25:
                    stats["bearish_mentions"] += 1

            for ticker in tickers:
                stats = ticker_stats[ticker]
                stats["score_total"] += score
                stats["mention_count"] += 1
                if score >= 0.25:
                    stats["bullish_mentions"] += 1
                elif score <= -0.25:
                    stats["bearish_mentions"] += 1
                if channel:
                    stats["channels"].add(channel)
                for theme in themes:
                    stats["reasons"].add(f"theme:{theme}")
                source = item.get("source")
                if source:
                    stats["reasons"].add(source)

        top_themes = self._build_theme_rows(theme_stats)
        top_tickers = self._build_ticker_rows(ticker_stats)

        return {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "themes": top_themes[:5],
            "tickers": top_tickers[:5],
            "overall_action": self._overall_action(top_tickers),
        }

    def _build_theme_rows(self, theme_stats):
        rows = []
        for theme, stats in theme_stats.items():
            avg_score = stats["score_total"] / max(stats["video_count"], 1)
            action = self._score_action(avg_score)
            rows.append(
                {
                    "name": theme,
                    "score": round(avg_score, 2),
                    "video_count": stats["video_count"],
                    "bullish_mentions": stats["bullish_mentions"],
                    "bearish_mentions": stats["bearish_mentions"],
                    "action": action,
                }
            )
        rows.sort(key=lambda item: (abs(item["score"]), item["video_count"]), reverse=True)
        return rows

    def _build_ticker_rows(self, ticker_stats):
        rows = []
        for ticker, stats in ticker_stats.items():
            avg_score = stats["score_total"] / max(stats["mention_count"], 1)
            watch_score = round(
                stats["mention_count"] + avg_score + (len(stats["channels"]) * 0.3),
                2,
            )
            rows.append(
                {
                    "ticker": ticker,
                    "score": watch_score,
                    "avg_sentiment": round(avg_score, 2),
                    "mention_count": stats["mention_count"],
                    "channel_count": len(stats["channels"]),
                    "action": self._score_action(avg_score),
                    "reasons": sorted(stats["reasons"])[:5],
                }
            )
        rows.sort(key=lambda item: (item["score"], abs(item["avg_sentiment"])), reverse=True)
        return rows

    def _score_action(self, score):
        if score <= -0.4:
            return "AVOID"
        if score >= 0.25:
            return "WATCH"
        return "NO SIGNAL"

    def _overall_action(self, ticker_rows):
        if not ticker_rows:
            return "NO SIGNAL"
        actions = {item.get("action") for item in ticker_rows[:3]}
        if "WATCH" in actions:
            return "WATCH"
        if "AVOID" in actions:
            return "AVOID"
        return "NO SIGNAL"

    def _safe_float(self, value):
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0
