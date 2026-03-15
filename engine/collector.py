from datetime import datetime

import feedparser
import yfinance as yf


class DataCollector:
    def __init__(self, tickers=None):
        self.tickers = tickers or ["6501", "7203", "8035"]

    def fetch_market_data(self):
        market_context = {}
        for ticker in self.tickers:
            symbol = self._format_ticker(ticker)
            ticker_data = yf.Ticker(symbol)
            hist = ticker_data.history(period="5d")
            if hist.empty or len(hist["Close"]) < 2:
                continue

            current_price = hist["Close"].iloc[-1]
            prev_price = hist["Close"].iloc[-2]
            change = (current_price - prev_price) / prev_price
            market_context[ticker] = {
                "price": round(current_price, 1),
                "change_rate": round(change * 100, 2),
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }
        return market_context

    def fetch_news(self, feeds=None):
        if not feeds:
            feeds = {
                "Reuters": "https://www.reutersagency.com/feed/?best-topics=business-finance&post_type=best",
                "Nikkei": "https://www.nikkei.com/rss/news/index.xml",
            }

        collected_news = []
        for name, url in feeds.items():
            feed = feedparser.parse(url)
            for entry in feed.entries[:2]:
                collected_news.append(
                    {
                        "source": name,
                        "title": getattr(entry, "title", ""),
                        "link": getattr(entry, "link", ""),
                        "published": getattr(entry, "published", "N/A"),
                    }
                )
        return collected_news

    def _format_ticker(self, ticker):
        if "." in ticker or "-" in ticker or "=" in ticker:
            return ticker
        return f"{ticker}.T"
