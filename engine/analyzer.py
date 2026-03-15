import json
import os
import time
from datetime import datetime, timedelta, timezone

import requests


class AIAnalyzer:
    def __init__(self):
        self.api_enabled = False
        self.request_timeout = int(os.getenv("GEMINI_REQUEST_TIMEOUT_SECONDS", "10"))
        self.max_retries = int(os.getenv("GEMINI_MAX_RETRIES", "2"))
        self.retry_backoff_seconds = float(
            os.getenv("GEMINI_RETRY_BACKOFF_SECONDS", "3")
        )
        self.cooldown_seconds = int(os.getenv("GEMINI_COOLDOWN_SECONDS", "300"))
        self.api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
        self.base_url = "https://generativelanguage.googleapis.com/v1beta/models"
        self.cooldown_path = os.path.join("data", "gemini_cooldown.json")
        if self.api_key and self.api_key != "your_google_api_key_here":
            self.api_enabled = True
        else:
            self.api_key = None
            print("GOOGLE_API_KEY is not configured. Running in mock mode.")

    def analyze_sentiment(self, text):
        if not self.api_enabled:
            return {
                "score": 0.0,
                "reason": "mock mode: GOOGLE_API_KEY not configured",
            }
        cooldown_reason = self._get_cooldown_reason()
        if cooldown_reason:
            return {"score": 0.0, "reason": cooldown_reason}

        prompt = (
            "Analyze the sentiment of the following YouTube-related text for market impact. "
            "Return JSON with keys score and reason. "
            "Score must be between -1.0 and 1.0.\n\n"
            f"Text:\n{text}"
        )
        try:
            response_text = self._generate_content("gemini-2.5-flash", prompt)
            if not response_text:
                return {"score": 0.0, "reason": "sentiment analysis timeout"}
            return self._parse_json_response(
                response_text,
                {"score": 0.0, "reason": "failed to parse sentiment response"},
            )
        except Exception as exc:
            print(f"Sentiment analysis failed: {exc}")
            return {"score": 0.0, "reason": "sentiment analysis error"}

    def consult_council(self, data_context):
        if not self.api_enabled:
            return []
        if self._get_cooldown_reason():
            return []

        compact_context = self._compact_context(data_context)
        if not compact_context.get("market"):
            return []
        if not compact_context.get("news") and not compact_context.get("youtube"):
            return []
        prompt = (
            "You are an investment council. Review the following market, news, YouTube, "
            "and portfolio context. Return a JSON array of trade decisions. "
            "Return at most 3 items. Prefer wait if evidence is weak. "
            "Each item must contain ticker, action, confidence, logic, sl_rate, and tp_rate.\n\n"
            f"Context:\n{json.dumps(compact_context, ensure_ascii=False, indent=2)}"
        )
        try:
            response_text = self._generate_content("gemini-2.0-flash", prompt)
            if not response_text:
                return []
            return self._parse_json_response(response_text, [])
        except Exception as exc:
            print(f"Council analysis failed: {exc}")
            return []

    def _generate_content(self, model, prompt):
        url = f"{self.base_url}/{model}:generateContent?key={self.api_key}"
        payload = {
            "contents": [
                {
                    "parts": [
                        {
                            "text": prompt,
                        }
                    ]
                }
            ]
        }
        last_error = None
        for attempt in range(self.max_retries + 1):
            try:
                response = requests.post(
                    url, json=payload, timeout=self.request_timeout
                )
                response.raise_for_status()
                data = response.json()
                candidates = data.get("candidates", [])
                if not candidates:
                    return None
                parts = candidates[0].get("content", {}).get("parts", [])
                texts = [part.get("text", "") for part in parts if part.get("text")]
                return "\n".join(texts).strip() if texts else None
            except requests.HTTPError as exc:
                last_error = exc
                status_code = exc.response.status_code if exc.response else None
                if status_code == 429:
                    self._set_cooldown()
                if status_code != 429 or attempt >= self.max_retries:
                    raise
                sleep_seconds = self.retry_backoff_seconds * (attempt + 1)
                print(
                    f"Gemini rate limited for {model}. retry {attempt + 1}/{self.max_retries} "
                    f"after {sleep_seconds:.1f}s"
                )
                time.sleep(sleep_seconds)
            except requests.RequestException as exc:
                last_error = exc
                if attempt >= self.max_retries:
                    raise
                sleep_seconds = self.retry_backoff_seconds * (attempt + 1)
                print(
                    f"Gemini request retry for {model}. retry {attempt + 1}/{self.max_retries} "
                    f"after {sleep_seconds:.1f}s"
                )
                time.sleep(sleep_seconds)
        if last_error:
            raise last_error
        return None

    def _get_cooldown_reason(self):
        if not os.path.exists(self.cooldown_path):
            return None
        try:
            with open(self.cooldown_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            until_text = data.get("cooldown_until")
            if not until_text:
                return None
            cooldown_until = datetime.fromisoformat(until_text)
            now = datetime.now(timezone.utc)
            if cooldown_until <= now:
                return None
            remaining = int((cooldown_until - now).total_seconds())
            return f"gemini cooldown active ({remaining}s remaining)"
        except Exception:
            return None

    def _set_cooldown(self):
        os.makedirs(os.path.dirname(self.cooldown_path), exist_ok=True)
        cooldown_until = datetime.now(timezone.utc) + timedelta(
            seconds=self.cooldown_seconds
        )
        data = {"cooldown_until": cooldown_until.isoformat()}
        with open(self.cooldown_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _parse_json_response(self, text, fallback):
        cleaned = text.strip().strip("`")
        if cleaned.startswith("json"):
            cleaned = cleaned[4:].strip()
        try:
            return json.loads(cleaned)
        except Exception:
            return fallback

    def _compact_context(self, data_context):
        news_items = []
        for item in data_context.get("news", [])[:5]:
            news_items.append(
                {
                    "source": item.get("source"),
                    "title": item.get("title"),
                    "published": item.get("published"),
                }
            )

        youtube_items = []
        for item in data_context.get("youtube", [])[:3]:
            sentiment = item.get("sentiment", {})
            youtube_items.append(
                {
                    "title": item.get("title"),
                    "channel": item.get("channel"),
                    "source": item.get("source"),
                    "sentiment_score": sentiment.get("score"),
                    "sentiment_reason": sentiment.get("reason"),
                }
            )

        portfolio = data_context.get("portfolio", {})
        holdings = portfolio.get("holdings", {})
        compact_holdings = {}
        for ticker, item in holdings.items():
            compact_holdings[ticker] = {
                "quantity": item.get("quantity"),
                "avg_price": item.get("avg_price"),
                "sl_price": item.get("sl_price"),
                "tp_price": item.get("tp_price"),
            }

        return {
            "market": data_context.get("market", {}),
            "news": news_items,
            "youtube": youtube_items,
            "portfolio": {
                "cash": portfolio.get("cash"),
                "holdings": compact_holdings,
            },
        }
