import json
import os
import time
from datetime import datetime, timedelta, timezone

import requests


SENTIMENT_RESPONSE_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "score": {"type": "NUMBER"},
        "reason": {"type": "STRING"},
    },
    "required": ["score", "reason"],
    "propertyOrdering": ["score", "reason"],
}

TRADE_PROPOSALS_RESPONSE_SCHEMA = {
    "type": "ARRAY",
    "items": {
        "type": "OBJECT",
        "properties": {
            "ticker": {"type": "STRING"},
            "action": {"type": "STRING"},
            "confidence": {"type": "NUMBER"},
            "logic": {"type": "STRING"},
        },
        "required": ["ticker", "action", "confidence", "logic"],
        "propertyOrdering": ["ticker", "action", "confidence", "logic"],
    },
}

COUNCIL_DECISIONS_RESPONSE_SCHEMA = {
    "type": "ARRAY",
    "items": {
        "type": "OBJECT",
        "properties": {
            "ticker": {"type": "STRING"},
            "action": {"type": "STRING"},
            "confidence": {"type": "NUMBER"},
            "logic": {"type": "STRING"},
            "sl_rate": {"type": "NUMBER", "nullable": True},
            "tp_rate": {"type": "NUMBER", "nullable": True},
        },
        "required": ["ticker", "action", "confidence", "logic"],
        "propertyOrdering": [
            "ticker",
            "action",
            "confidence",
            "logic",
            "sl_rate",
            "tp_rate",
        ],
    },
}


class AIAnalyzer:
    def __init__(self):
        self.api_enabled = False
        self.request_timeout = int(os.getenv("GEMINI_REQUEST_TIMEOUT_SECONDS", "10"))
        self.max_retries = int(os.getenv("GEMINI_MAX_RETRIES", "2"))
        self.sentiment_model = os.getenv(
            "GEMINI_SENTIMENT_MODEL", "gemini-2.5-flash-lite"
        )
        self.proposal_model = os.getenv("GEMINI_PROPOSAL_MODEL", "gemini-2.0-flash")
        self.council_model = os.getenv("GEMINI_COUNCIL_MODEL", "gemini-2.0-flash")
        self.sentiment_fallback_models = self._parse_model_fallbacks(
            os.getenv("GEMINI_SENTIMENT_FALLBACK_MODELS", "gemini-2.5-flash-lite")
        )
        self.proposal_fallback_models = self._parse_model_fallbacks(
            os.getenv(
                "GEMINI_PROPOSAL_FALLBACK_MODELS",
                "gemini-2.5-flash,gemini-2.5-flash-lite",
            )
        )
        self.council_fallback_models = self._parse_model_fallbacks(
            os.getenv(
                "GEMINI_COUNCIL_FALLBACK_MODELS",
                "gemini-2.5-flash,gemini-2.5-flash-lite",
            )
        )
        self.sentiment_request_limit = int(
            os.getenv("GEMINI_SENTIMENT_REQUEST_LIMIT", "3")
        )
        self.retry_backoff_seconds = float(
            os.getenv("GEMINI_RETRY_BACKOFF_SECONDS", "3")
        )
        self.cooldown_seconds = int(os.getenv("GEMINI_COOLDOWN_SECONDS", "300"))
        self.api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
        self.base_url = "https://generativelanguage.googleapis.com/v1beta/models"
        self.cooldown_path = os.path.join("data", "gemini_cooldown.json")
        self.sentiment_requests_used = 0
        self.sequential_sentiment_mode = True
        self.available_models = None
        if self.api_key and self.api_key != "your_google_api_key_here":
            self.api_enabled = True
            self.available_models = self._list_available_models()
            self.sentiment_model = self._resolve_model(
                self.sentiment_model, self.sentiment_fallback_models
            )
            self.proposal_model = self._resolve_model(
                self.proposal_model, self.proposal_fallback_models
            )
            self.council_model = self._resolve_model(
                self.council_model, self.council_fallback_models
            )
            print(
                "Gemini models: "
                f"sentiment={self.sentiment_model}, "
                f"proposal={self.proposal_model}, "
                f"council={self.council_model}"
            )
        else:
            self.api_key = None
            print("GOOGLE_API_KEY is not configured. Running in mock mode.")

    def build_runtime_info(self):
        cooldown_reason = self._get_cooldown_reason()
        return {
            "api_enabled": self.api_enabled,
            "sentiment_model": self.sentiment_model,
            "proposal_model": self.proposal_model,
            "council_model": self.council_model,
            "request_timeout": self.request_timeout,
            "max_retries": self.max_retries,
            "retry_backoff_seconds": self.retry_backoff_seconds,
            "cooldown_seconds": self.cooldown_seconds,
            "sentiment_request_limit": self.sentiment_request_limit,
            "sentiment_requests_used": self.sentiment_requests_used,
            "cooldown_reason": cooldown_reason,
        }

    def analyze_sentiment(self, text):
        if not self.api_enabled:
            return {
                "score": 0.0,
                "reason": "mock mode: GOOGLE_API_KEY not configured",
            }
        cooldown_reason = self._get_cooldown_reason()
        if cooldown_reason:
            return {"score": 0.0, "reason": cooldown_reason}
        if (
            self.sentiment_request_limit >= 0
            and self.sentiment_requests_used >= self.sentiment_request_limit
        ):
            return {
                "score": 0.0,
                "reason": (
                    "sentiment request budget reached "
                    f"({self.sentiment_requests_used}/{self.sentiment_request_limit})"
                ),
            }
        self.sentiment_requests_used += 1

        prompt = (
            "Analyze the sentiment of the following YouTube-related text for market impact. "
            "Return JSON with keys score and reason. "
            "Score must be between -1.0 and 1.0.\n\n"
            f"Text:\n{text}"
        )
        try:
            response_text = self._generate_content(
                self.sentiment_model,
                prompt,
                response_schema=SENTIMENT_RESPONSE_SCHEMA,
            )
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
        if compact_context.get("shortlisted_candidates") == [] and compact_context.get("ai_proposals"):
            return []
        prompt = (
            "You are an investment council. Review the following market, news, YouTube, "
            "AI proposals, shortlisted candidates, watchlist, and portfolio context. "
            "Return a JSON array of trade decisions. "
            "Return at most 3 items. Prefer wait if evidence is weak. "
            "When shortlisted_candidates are present, only consider those tickers for BUY or SELL. "
            "Each item must contain ticker, action, confidence, logic, sl_rate, and tp_rate.\n\n"
            f"Context:\n{json.dumps(compact_context, ensure_ascii=False, indent=2)}"
        )
        try:
            response_text = self._generate_content(
                self.council_model,
                prompt,
                response_schema=COUNCIL_DECISIONS_RESPONSE_SCHEMA,
            )
            if not response_text:
                return []
            parsed = self._parse_json_response(response_text, [])
            return self._normalize_council_decisions(parsed)
        except Exception as exc:
            print(f"Council analysis failed: {exc}")
            return []

    def propose_trade_candidates(self, data_context):
        if not self.api_enabled:
            return []
        if self._get_cooldown_reason():
            return []

        compact_context = self._compact_context(data_context)
        watchlist = compact_context.get("watchlist", {})
        if not watchlist.get("tickers"):
            return []
        if watchlist.get("overall_action") == "NO SIGNAL" and not any(
            item.get("action") in {"WATCH", "AVOID"} for item in watchlist.get("tickers", [])
        ):
            return []

        prompt = (
            "You are an AI trading assistant. Review the following market, news, YouTube, and watchlist context. "
            "Propose up to 3 candidate tickers and label each as BUY, WATCH, AVOID, or NO SIGNAL. "
            "BUY should be used only when evidence is strong. "
            "Return a JSON array. Each item must contain ticker, action, confidence, and logic.\n\n"
            f"Context:\n{json.dumps(compact_context, ensure_ascii=False, indent=2)}"
        )
        try:
            response_text = self._generate_content(
                self.proposal_model,
                prompt,
                response_schema=TRADE_PROPOSALS_RESPONSE_SCHEMA,
            )
            if not response_text:
                return []
            parsed = self._parse_json_response(response_text, [])
            return self._normalize_trade_proposals(parsed)
        except Exception as exc:
            print(f"AI proposal generation failed: {exc}")
            return []

    def _generate_content(self, model, prompt, response_schema=None):
        url = f"{self.base_url}/{model}:generateContent?key={self.api_key}"
        payload = self._build_generation_payload(prompt, response_schema=response_schema)
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
                error_body = ""
                if exc.response is not None:
                    try:
                        error_body = exc.response.text[:500]
                    except Exception:
                        error_body = ""
                if status_code == 429:
                    self._set_cooldown()
                if status_code != 429 or attempt >= self.max_retries:
                    if error_body:
                        print(f"Gemini error body ({model}): {error_body}")
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

    def _build_generation_payload(self, prompt, response_schema=None):
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
        if response_schema:
            payload["generationConfig"] = {
                "responseMimeType": "application/json",
                "responseSchema": response_schema,
            }
        return payload

    def _list_available_models(self):
        try:
            response = requests.get(
                f"{self.base_url}?key={self.api_key}",
                timeout=self.request_timeout,
            )
            response.raise_for_status()
            data = response.json()
            models = set()
            for item in data.get("models", []):
                name = str(item.get("name", ""))
                if name.startswith("models/"):
                    models.add(name.split("models/", 1)[1])
            return models or None
        except requests.RequestException as exc:
            print(f"Gemini model list lookup failed: {exc}")
            return None

    def _resolve_model(self, preferred, fallbacks):
        if not self.available_models:
            return preferred
        candidates = [preferred] + [item for item in fallbacks if item != preferred]
        for model in candidates:
            if model in self.available_models:
                if model != preferred:
                    print(f"Gemini model fallback: {preferred} -> {model}")
                return model
        return preferred

    def _parse_model_fallbacks(self, raw):
        values = []
        for item in str(raw or "").split(","):
            model = item.strip()
            if model and model not in values:
                values.append(model)
        return values

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

    def _normalize_trade_proposals(self, parsed):
        if not isinstance(parsed, list):
            return []
        normalized = []
        allowed_actions = {"BUY", "WATCH", "AVOID", "NO SIGNAL", "SELL"}
        for item in parsed[:5]:
            if not isinstance(item, dict):
                continue
            ticker = str(item.get("ticker", "")).strip().upper()
            action = str(item.get("action", "")).strip().upper()
            if not ticker or action not in allowed_actions:
                continue
            confidence = self._bounded_confidence(item.get("confidence"))
            logic = str(item.get("logic", "")).strip() or "no logic provided"
            normalized.append(
                {
                    "ticker": ticker,
                    "action": action,
                    "confidence": confidence,
                    "logic": logic,
                }
            )
        return normalized[:3]

    def _normalize_council_decisions(self, parsed):
        if not isinstance(parsed, list):
            return []
        normalized = []
        allowed_actions = {"buy", "sell", "watch", "avoid", "wait", "no signal"}
        for item in parsed[:5]:
            if not isinstance(item, dict):
                continue
            ticker = str(item.get("ticker", "")).strip().upper()
            action = str(item.get("action", "")).strip().lower()
            if not ticker or action not in allowed_actions:
                continue
            confidence = self._bounded_confidence(item.get("confidence"))
            logic = str(item.get("logic", "")).strip() or "no logic provided"
            normalized.append(
                {
                    "ticker": ticker,
                    "action": action,
                    "confidence": confidence,
                    "logic": logic,
                    "sl_rate": self._safe_rate(item.get("sl_rate")),
                    "tp_rate": self._safe_rate(item.get("tp_rate")),
                }
            )
        return normalized[:3]

    def _bounded_confidence(self, value):
        try:
            confidence = float(value)
        except (TypeError, ValueError):
            return 0.0
        return round(max(0.0, min(confidence, 1.0)), 2)

    def _safe_rate(self, value):
        try:
            rate = float(value)
        except (TypeError, ValueError):
            return None
        if rate <= 0:
            return None
        return round(rate, 4)

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
            "watchlist": self._compact_watchlist(data_context.get("watchlist", {})),
            "confirmed_watch_tickers": data_context.get("confirmed_watch_tickers", [])[:10],
            "ai_proposals": data_context.get("ai_proposals", [])[:5],
            "shortlisted_candidates": data_context.get("shortlisted_candidates", [])[:5],
            "portfolio": {
                "cash": portfolio.get("cash"),
                "holdings": compact_holdings,
            },
        }

    def _compact_watchlist(self, watchlist):
        if not watchlist:
            return {}
        return {
            "overall_action": watchlist.get("overall_action"),
            "source_summary": {
                "fixed_channel_items": ((watchlist.get("source_summary") or {}).get("fixed_channel_items", 0)),
                "search_items": ((watchlist.get("source_summary") or {}).get("search_items", 0)),
                "fixed_channel_count": ((watchlist.get("source_summary") or {}).get("fixed_channel_count", 0)),
                "search_keyword_count": ((watchlist.get("source_summary") or {}).get("search_keyword_count", 0)),
                "top_fixed_channels": ((watchlist.get("source_summary") or {}).get("top_fixed_channels", []))[:3],
            },
            "themes": [
                {
                    "name": item.get("name"),
                    "action": item.get("action"),
                    "score": item.get("score"),
                    "video_count": item.get("video_count"),
                    "group_count": item.get("group_count"),
                    "fixed_source_count": item.get("fixed_source_count"),
                    "search_source_count": item.get("search_source_count"),
                    "top_fixed_channels": (item.get("top_fixed_channels") or [])[:2],
                }
                for item in watchlist.get("themes", [])[:3]
            ],
            "tickers": [
                {
                    "ticker": item.get("ticker"),
                    "action": item.get("action"),
                    "score": item.get("score"),
                    "avg_sentiment": item.get("avg_sentiment"),
                    "mention_count": item.get("mention_count"),
                    "group_count": item.get("group_count"),
                    "fixed_source_count": item.get("fixed_source_count"),
                    "search_source_count": item.get("search_source_count"),
                    "top_fixed_channels": (item.get("top_fixed_channels") or [])[:2],
                    "reasons": (item.get("reasons") or [])[:3],
                }
                for item in watchlist.get("tickers", [])[:5]
            ],
        }
