import os
import sys
import json
import time
from dotenv import load_dotenv

sys.path.append(os.getcwd())

from engine.collector import DataCollector
from engine.analyzer import AIAnalyzer
from engine.broker import MockBroker
from engine.patrol_store import PatrolStore
from engine.youtube_analyzer import YouTubeAnalyzer


def load_config():
    config_path = "infra/config/app_config.json"
    if os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def main():
    print("YouTube Patrol v2.0 starting...")

    if os.path.exists("infra/.env"):
        load_dotenv("infra/.env")
    else:
        load_dotenv()

    config = load_config()
    tickers = config.get("target_tickers", ["6501", "7203"])
    patrol_store = PatrolStore(data_dir="data")
    latest_watchlist = patrol_store.load_latest_watchlist() or {}
    watchlist_rules = config.get("watchlist_rules", {})
    watch_tickers = [
        item.get("ticker")
        for item in latest_watchlist.get("tickers", [])[:5]
        if item.get("ticker") and item.get("action") == "WATCH"
    ]
    tickers = list(dict.fromkeys(tickers + watch_tickers))

    collector = DataCollector(tickers=tickers)
    analyzer = AIAnalyzer()
    broker = MockBroker(data_dir="data")

    print(f"Tickers: {', '.join(tickers)}")
    print("Fetching market/news...")
    market_data = collector.fetch_market_data()
    news_data = collector.fetch_news(feeds=config.get("news_feeds"))
    confirmed_watch_tickers = confirmed_by_price(
        latest_watchlist, market_data, watchlist_rules
    )

    print("Risk monitor check...")
    alerts = broker.monitor_and_execute(market_data)
    for alert in alerts:
        print(f"!!! {alert['reason']} !!!")

    print("Analyzing YouTube + council...")
    youtube_sentiment = []
    youtube_targets = config.get("youtube_patrol_targets", {})
    youtube_max = config.get("youtube_max_videos", 3)
    youtube_enabled = config.get("enable_youtube_analysis", False)
    if youtube_enabled and youtube_targets and analyzer.api_enabled:
        youtube_analyzer = YouTubeAnalyzer(youtube_targets, max_videos=youtube_max)
        youtube_sentiment = youtube_analyzer.analyze(analyzer)

    context = {
        "market": market_data,
        "news": news_data,
        "youtube": youtube_sentiment,
        "watchlist": latest_watchlist,
        "confirmed_watch_tickers": confirmed_watch_tickers,
        "portfolio": broker.portfolio,
    }

    decisions = analyzer.consult_council(context)
    decisions = filter_decisions_by_watchlist(
        decisions, latest_watchlist, confirmed_watch_tickers, watchlist_rules
    )
    print(f"Council decisions: {len(decisions)}")

    for d in decisions:
        action = d.get("action", "wait").lower()
        if action in ["buy", "sell"]:
            price = market_data.get(d["ticker"], {}).get("price", 1000)

            sl_rate = d.get("sl_rate") or config.get("risk", {}).get(
                "default_stop_loss", 0.05
            )
            tp_rate = d.get("tp_rate") or config.get("risk", {}).get(
                "default_profit_taking", 0.15
            )

            sl_p = price * (1 - sl_rate) if action == "buy" else None
            tp_p = price * (1 + tp_rate) if action == "buy" else None

            broker.place_order(
                ticker=d["ticker"],
                action=action,
                quantity=100,
                price=price,
                rationale=d.get("logic", "No reason provided"),
                sl_price=sl_p,
                tp_price=tp_p,
            )

    result = patrol_store.save_run(
        {
            "market": market_data,
            "news": news_data,
            "youtube": youtube_sentiment,
            "watchlist": latest_watchlist,
            "confirmed_watch_tickers": confirmed_watch_tickers,
            "decisions": decisions,
            "portfolio": broker.portfolio,
        }
    )
    webhook_url = os.getenv("DISCORD_WEBHOOK_URL")
    notified = patrol_store.notify_if_configured(result, webhook_url)
    print(f"Report saved: {result['report_path']}")
    print(f"Snapshot saved: {result['history_path']}")
    print(f"Webhook notified: {notified}")

    print("Patrol complete.")


def confirmed_by_price(watchlist, market_data, watchlist_rules):
    if not watchlist_rules.get("buy_requires_price_confirmation", False):
        return []
    min_change = float(watchlist_rules.get("min_price_confirmation_change_pct", 0.5))
    confirmed = []
    for item in watchlist.get("tickers", [])[:10]:
        if item.get("action") != "WATCH":
            continue
        ticker = item.get("ticker")
        change_rate = market_data.get(ticker, {}).get("change_rate")
        if change_rate is None:
            continue
        if change_rate >= min_change:
            confirmed.append(ticker)
    return confirmed


def filter_decisions_by_watchlist(decisions, watchlist, confirmed_watch_tickers, watchlist_rules):
    if not decisions:
        return []
    if not watchlist_rules.get("buy_requires_price_confirmation", False):
        return decisions
    watch_tickers = {
        item.get("ticker")
        for item in watchlist.get("tickers", [])[:10]
        if item.get("ticker")
    }
    confirmed = set(confirmed_watch_tickers)
    filtered = []
    for item in decisions:
        action = str(item.get("action", "")).lower()
        ticker = item.get("ticker")
        if action == "buy" and ticker in watch_tickers and ticker not in confirmed:
            item = dict(item)
            item["action"] = "watch"
            item["logic"] = f"{item.get('logic', '')} price confirmation missing".strip()
        filtered.append(item)
    return filtered


if __name__ == "__main__":
    main()
