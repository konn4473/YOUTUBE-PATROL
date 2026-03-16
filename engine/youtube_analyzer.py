from concurrent.futures import ThreadPoolExecutor, TimeoutError

import yt_dlp
from youtube_transcript_api import YouTubeTranscriptApi


class YouTubeAnalyzer:
    def __init__(self, targets, max_videos=3, languages=None, theme_ticker_map=None):
        self.channels = targets.get("channels", [])
        self.search_keywords = targets.get("search_keywords", [])
        self.max_videos = max_videos
        self.max_items = targets.get("max_items", 3)
        self.languages = languages or ["ja", "en"]
        self.theme_ticker_map = theme_ticker_map or {}
        self.request_timeout = targets.get("request_timeout_seconds", 15)
        self.ydl = yt_dlp.YoutubeDL(
            {
                "quiet": True,
                "no_warnings": True,
                "skip_download": True,
                "noplaylist": True,
                "extract_flat": True,
                "socket_timeout": self.request_timeout,
            }
        )

    def collect_targets(self):
        results = []
        seen = set()

        for ch in self.channels:
            channel_url = self._resolve_channel_url(ch)
            if not channel_url:
                continue
            for v in self._extract_channel_videos(channel_url):
                if v["video_id"] in seen:
                    continue
                v["source"] = f"channel:{ch.get('name', channel_url)}"
                results.append(v)
                seen.add(v["video_id"])

        for kw in self.search_keywords:
            for v in self._search_videos(kw):
                if v["video_id"] in seen:
                    continue
                v["source"] = f"search:{kw}"
                results.append(v)
                seen.add(v["video_id"])

        return results[: self.max_items]

    def analyze(self, ai_analyzer):
        analyzed = []
        for v in self.collect_targets():
            transcript = self._fetch_transcript(v["video_id"])
            text = self._build_text(v, transcript)
            if len(text) > 6000:
                text = text[:6000]
            if text.strip():
                sentiment = ai_analyzer.analyze_sentiment(text)
            else:
                sentiment = {"score": 0.0, "reason": "no text"}
            themes = self._infer_themes(v, transcript, sentiment)
            candidate_tickers = self._map_tickers(themes)
            analyzed.append(
                {
                    "video_id": v["video_id"],
                    "title": v.get("title"),
                    "channel": v.get("channel"),
                    "published": v.get("published"),
                    "source": v.get("source"),
                    "sentiment": sentiment,
                    "themes": themes,
                    "candidate_tickers": candidate_tickers,
                    "confidence": self._confidence(sentiment, themes, candidate_tickers),
                }
            )
        return analyzed

    def _extract_channel_videos(self, channel_url):
        try:
            info = self._run_with_timeout(
                lambda: self.ydl.extract_info(channel_url, download=False)
            )
            if not info:
                return []
            entries = info.get("entries", [])[: self.max_videos]
            return [self._normalize_entry(e) for e in entries if e]
        except Exception:
            return []

    def _search_videos(self, keyword):
        try:
            query = f"ytsearch{self.max_videos}:{keyword}"
            info = self._run_with_timeout(
                lambda: self.ydl.extract_info(query, download=False)
            )
            if not info:
                return []
            entries = info.get("entries", [])
            return [self._normalize_entry(e) for e in entries if e]
        except Exception:
            return []

    def _normalize_entry(self, entry):
        return {
            "video_id": entry.get("id"),
            "title": entry.get("title"),
            "channel": entry.get("channel") or entry.get("uploader"),
            "published": entry.get("upload_date"),
            "description": entry.get("description") or "",
        }

    def _resolve_channel_url(self, channel):
        if channel.get("url"):
            return channel["url"]
        if channel.get("handle"):
            return f"https://www.youtube.com/@{channel['handle']}/videos"
        if channel.get("id"):
            return f"https://www.youtube.com/channel/{channel['id']}/videos"
        return None

    def _fetch_transcript(self, video_id):
        try:
            transcript = self._run_with_timeout(
                lambda: YouTubeTranscriptApi.get_transcript(
                    video_id, languages=self.languages
                )
            )
            if not transcript:
                return None
            return " ".join([item.get("text", "") for item in transcript])
        except Exception:
            return None

    def _build_text(self, video, transcript):
        parts = []
        if video.get("title"):
            parts.append(video["title"])
        if video.get("description"):
            parts.append(video["description"])
        if transcript:
            parts.append(transcript)
        return "\n".join(parts)

    def _run_with_timeout(self, func):
        executor = ThreadPoolExecutor(max_workers=1)
        future = executor.submit(func)
        try:
            return future.result(timeout=self.request_timeout)
        except TimeoutError:
            future.cancel()
            return None
        finally:
            executor.shutdown(wait=False, cancel_futures=True)

    def _infer_themes(self, video, transcript, sentiment):
        text = " ".join(
            str(part)
            for part in [
                video.get("title", ""),
                video.get("description", ""),
                video.get("source", ""),
                transcript or "",
                (sentiment or {}).get("reason", ""),
            ]
            if part
        ).lower()
        keyword_map = [
            ("日本株", ["日本株", "日経", "nikkei", "japan equities"]),
            ("半導体", ["半導体", "semiconductor", "半導体株"]),
            ("防衛", ["防衛", "defense", "防衛関連"]),
            ("商社", ["商社", "trading house"]),
            ("銀行", ["銀行", "bank", "メガバンク"]),
            ("原油", ["原油", "wti", "oil", "crude"]),
            ("円安", ["円安", "ドル円", "usd/jpy", "yen"]),
            ("米国株", ["米国株", "nasdaq", "s&p", "dow"]),
            ("仮想通貨", ["仮想通貨", "bitcoin", "btc", "crypto"]),
            ("AI", ["ai", "人工知能"]),
        ]
        themes = []
        for theme, keywords in keyword_map:
            if any(keyword in text for keyword in keywords):
                themes.append(theme)
        return themes[:5]

    def _map_tickers(self, themes):
        tickers = []
        seen = set()
        for theme in themes:
            for ticker in self.theme_ticker_map.get(theme, []):
                if ticker in seen:
                    continue
                tickers.append(ticker)
                seen.add(ticker)
        return tickers[:6]

    def _confidence(self, sentiment, themes, candidate_tickers):
        try:
            score = abs(float((sentiment or {}).get("score", 0.0)))
        except (TypeError, ValueError):
            score = 0.0
        confidence = min(1.0, score + (0.1 * len(themes)) + (0.05 * len(candidate_tickers)))
        return round(confidence, 2)
