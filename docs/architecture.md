# YouTubeパトロール v2.0：アーキテクチャ設計書

## プロジェクト目標
YouTubeの感情分析、リアルタイムニュース、マーケットデータを統合し、AI投資委員会が自律的に投資判断を下すシステムの構築。買付時には自動的に逆指値（損切り・利確）を設定し、24時間資産を保護する。

## モジュール構成

### 1. Data Collection 層 (`engine/collector.py`)
- **YouTube Collector**: 指定されたチャンネルの最新動画を収集。
- **Market Collector**: yfinance を利用した株価・テクニカル指標の取得。
- **News Collector**: 主要ニュース配信サイトのRSSからヘッドラインを取得。

### 2. Analysis & Brain 層 (`engine/analyzer.py`, `engine/council.py`)
- **Emotion Analyzer**: Gemini 1.5 Flash による動画内容のセンチメント分析。
- **Investment Council**: Gemini 1.5 Pro による「YouTube主観 vs 数字・事実」の統合判断。

### 3. Execution & Risk 層 (`engine/broker.py`)
- **Mock Broker**: 仮想資産（100万円）の管理。
- **IFDOCO Manager**: 買付時の予約価格セットと、30分ごとの条件監視・強制執行。

## ディレクトリ・規約
- ルート直下にはファイルを作らず、必ず `engine/`, `infra/`, `docs/`, `data/` へ分類。
- 設定値は `infra/config/` 配下のJSONで一元管理される。
