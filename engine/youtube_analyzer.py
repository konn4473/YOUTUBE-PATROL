from concurrent.futures import ThreadPoolExecutor, TimeoutError
from datetime import datetime, timedelta

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
        self.recent_hours = int(targets.get("recent_hours", 24))
        self.parallel_workers = int(targets.get("parallel_workers", 2))
        self.use_transcripts = bool(targets.get("use_transcripts", False))
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
            for video in self._extract_channel_videos(channel_url):
                if video["video_id"] in seen:
                    continue
                video["source"] = f"channel:{ch.get('name', channel_url)}"
                video["channel_group"] = ch.get("group", "channel")
                video["channel_weight"] = ch.get("weight", 1.0)
                results.append(video)
                seen.add(video["video_id"])

        for keyword in self.search_keywords:
            for video in self._search_videos(keyword):
                if video["video_id"] in seen:
                    continue
                video["source"] = f"search:{keyword}"
                video["channel_group"] = "search"
                video["channel_weight"] = 0.7
                results.append(video)
                seen.add(video["video_id"])

        filtered = [video for video in results if self._is_recent(video.get("published"))]
        return filtered[: self.max_items]

    def analyze(self, ai_analyzer):
        videos = self.collect_targets()
        if not videos:
            return []

        def analyze_one(video):
            transcript = (
                self._fetch_transcript(video["video_id"])
                if self._should_fetch_transcript(video)
                else None
            )
            text = self._build_text(video, transcript)
            if len(text) > 6000:
                text = text[:6000]
            if text.strip():
                sentiment = ai_analyzer.analyze_sentiment(text)
            else:
                sentiment = {"score": 0.0, "reason": "no text"}
            themes = self._infer_themes(video, transcript, sentiment)
            candidate_tickers = self._map_tickers(themes)
            return {
                "video_id": video["video_id"],
                "title": video.get("title"),
                "channel": video.get("channel"),
                "published": video.get("published"),
                "source": video.get("source"),
                "channel_group": video.get("channel_group"),
                "channel_weight": video.get("channel_weight"),
                "sentiment": sentiment,
                "themes": themes,
                "candidate_tickers": candidate_tickers,
                "confidence": self._confidence(
                    sentiment, themes, candidate_tickers, video.get("channel_weight")
                ),
            }

        with ThreadPoolExecutor(max_workers=max(1, self.parallel_workers)) as executor:
            return list(executor.map(analyze_one, videos))

    def _extract_channel_videos(self, channel_url):
        try:
            info = self._run_with_timeout(
                lambda: self.ydl.extract_info(channel_url, download=False)
            )
            if not info:
                return []
            entries = info.get("entries", [])[: self.max_videos]
            return [self._normalize_entry(entry) for entry in entries if entry]
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
            return [self._normalize_entry(entry) for entry in entries if entry]
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
            return " ".join(item.get("text", "") for item in transcript)
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

    def _should_fetch_transcript(self, video):
        if not self.use_transcripts:
            return False
        seed_text = " ".join(
            str(part)
            for part in [video.get("title", ""), video.get("description", "")]
            if part
        )
        return len(seed_text) < 1200

    def _is_recent(self, published):
        if not published:
            return True
        try:
            if len(published) == 8:
                published_dt = datetime.strptime(published, "%Y%m%d")
            else:
                published_dt = datetime.fromisoformat(published)
        except ValueError:
            return True
        cutoff = datetime.now() - timedelta(hours=self.recent_hours)
        return published_dt >= cutoff

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
            if any(keyword.lower() in text for keyword in keywords):
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
        return tickers[:8]

    def _confidence(self, sentiment, themes, candidate_tickers, channel_weight):
        try:
            score = abs(float((sentiment or {}).get("score", 0.0)))
        except (TypeError, ValueError):
            score = 0.0
        try:
            weight = float(channel_weight or 1.0)
        except (TypeError, ValueError):
            weight = 1.0
        confidence = min(
            1.0,
            score
            + (0.08 * len(themes))
            + (0.04 * len(candidate_tickers))
            + (0.05 * weight),
        )
        return round(confidence, 2)
