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

    ai_proposals = analyzer.propose_trade_candidates(context)
    shortlisted_candidates = shortlist_ai_proposals(
        ai_proposals,
        latest_watchlist,
        market_data,
        news_data,
        confirmed_watch_tickers,
        watchlist_rules,
    )
    context["ai_proposals"] = ai_proposals
    context["shortlisted_candidates"] = shortlisted_candidates

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
            "ai_proposals": ai_proposals,
            "shortlisted_candidates": shortlisted_candidates,
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


def shortlist_ai_proposals(
    ai_proposals,
    watchlist,
    market_data,
    news_data,
    confirmed_watch_tickers,
    watchlist_rules,
):
    if not ai_proposals:
        return []

    confirmed = set(confirmed_watch_tickers)
    watchlist_rows = {item.get("ticker"): item for item in watchlist.get("tickers", [])[:10]}
    min_confidence = float(watchlist_rules.get("ai_proposal_min_confidence", 0.55))

    shortlisted = []
    for item in ai_proposals[:5]:
        ticker = item.get("ticker")
        action = str(item.get("action", "")).upper()
        confidence = _safe_float(item.get("confidence"))
        if not ticker or confidence < min_confidence:
            continue

        has_news = _has_related_news(ticker, news_data)
        market_item = market_data.get(ticker, {})
        change_rate = _safe_float(market_item.get("change_rate"))

        if action == "BUY":
            if ticker in watchlist_rows and ticker not in confirmed:
                item = dict(item)
                item["action"] = "WATCH"
                item["logic"] = f"{item.get('logic', '')} waiting for price confirmation".strip()
            elif not has_news and change_rate <= 0:
                item = dict(item)
                item["action"] = "WATCH"
                item["logic"] = f"{item.get('logic', '')} waiting for news or price support".strip()

        shortlisted.append(
            {
                "ticker": ticker,
                "action": item.get("action"),
                "confidence": round(confidence, 2),
                "logic": item.get("logic"),
                "has_news_support": has_news,
                "change_rate": change_rate,
            }
        )
    return shortlisted


def _has_related_news(ticker, news_data):
    if not news_data:
        return False
    ticker_hints = {
        "6501": ["hitachi", "日立"],
        "7203": ["toyota", "トヨタ"],
        "8035": ["tokyo electron", "東京エレクトロン", "半導体"],
        "1605": ["inpex", "原油", "石油"],
        "1662": ["原油", "oil", "wti"],
        "7011": ["三菱重工", "defense", "防衛"],
        "7012": ["川崎重工", "防衛"],
        "7013": ["ihi", "防衛"],
        "6857": ["advantest", "アドバンテスト", "半導体"],
        "6920": ["レーザーテック", "半導体"],
    }
    hints = ticker_hints.get(ticker, [ticker.lower()])
    for item in news_data[:10]:
        haystack = " ".join(
            str(part).lower()
            for part in [item.get("title", ""), item.get("source", "")]
            if part
        )
        if any(hint.lower() in haystack for hint in hints):
            return True
    return False


def _safe_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


if __name__ == "__main__":
    main()
