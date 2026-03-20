import json
import os
import sys
from dotenv import load_dotenv

sys.path.append(os.getcwd())

from engine.analyzer import AIAnalyzer
from engine.patrol_store import PatrolStore
from engine.watchlist_builder import WatchlistBuilder
from engine.youtube_analyzer import YouTubeAnalyzer


class _CooldownAnalyzer:
    def __init__(self, reason):
        self.reason = reason or "gemini cooldown active"
        self.shared_sentiment_result = {"score": 0.0, "reason": self.reason}

    def analyze_sentiment(self, text):
        return dict(self.shared_sentiment_result)


def load_config():
    config_path = "infra/config/app_config.json"
    if os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def main():
    print("YouTube patrol job starting...")

    if os.path.exists("infra/.env"):
        load_dotenv("infra/.env")
    else:
        load_dotenv()

    config = load_config()
    analyzer = AIAnalyzer()
    patrol_store = PatrolStore(data_dir="data")

    youtube_sentiment = []
    watchlist = {"timestamp": "", "themes": [], "tickers": [], "overall_action": "NO SIGNAL"}
    youtube_targets = config.get("youtube_patrol_targets", {})
    youtube_max = config.get("youtube_max_videos", 1)
    youtube_enabled = config.get("enable_youtube_job", False)
    theme_ticker_map = config.get("theme_ticker_map", {})
    watchlist_rules = config.get("watchlist_rules", {})

    if youtube_enabled and youtube_targets:
        youtube_analyzer = YouTubeAnalyzer(
            youtube_targets,
            max_videos=youtube_max,
            theme_ticker_map=theme_ticker_map,
        )
        active_analyzer = analyzer
        if not analyzer.api_enabled:
            print("Gemini API is unavailable. Running YouTube patrol in lightweight mode.")
            active_analyzer = _CooldownAnalyzer("mock mode: Gemini API unavailable")
        else:
            cooldown_reason = analyzer._get_cooldown_reason()
            if cooldown_reason:
                print(f"Gemini cooldown detected. Running YouTube patrol in lightweight mode: {cooldown_reason}")
                active_analyzer = _CooldownAnalyzer(cooldown_reason)
        youtube_sentiment = youtube_analyzer.analyze(active_analyzer)
        watchlist = WatchlistBuilder(theme_ticker_map, rules=watchlist_rules).build(
            youtube_sentiment
        )

    result = patrol_store.save_youtube_run(youtube_sentiment, watchlist=watchlist)
    webhook_url = os.getenv("DISCORD_WEBHOOK_URL")
    notified = patrol_store.notify_youtube_if_configured(result, webhook_url)
    print(f"YouTube report saved: {result['report_path']}")
    print(f"Watchlist report saved: {result['watchlist_report_path']}")
    print(f"YouTube snapshot saved: {result['history_path']}")
    print(f"Webhook notified: {notified}")
    print("YouTube patrol job complete.")


if __name__ == "__main__":
    main()
