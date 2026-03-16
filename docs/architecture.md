# YouTube Patrol v2.0 アーキテクチャ

## 目的
YouTube、ニュース、市場データを組み合わせて、売買を直接決めるのではなく、まず監視候補を作るための構成です。

基本方針は次です。

- YouTube は監視候補抽出に使う
- ニュースと価格で追認する
- 最終判断は council に寄せる

YouTube 単独での即時買い判断は行いません。

## レイヤ構成

### 1. Collection

- [engine/collector.py](/C:/AI/Share/youtube_patrol_v2/engine/collector.py)
  - 市場データ
  - RSS ニュース

- [engine/youtube_analyzer.py](/C:/AI/Share/youtube_patrol_v2/engine/youtube_analyzer.py)
  - チャンネル・検索キーワードから動画取得
  - 感情分析
  - テーマ抽出
  - 候補銘柄抽出
  - 直近 `recent_hours` 時間フィルタ
  - 並列解析

### 2. Watchlist

- [engine/watchlist_builder.py](/C:/AI/Share/youtube_patrol_v2/engine/watchlist_builder.py)
  - 動画結果を集計
  - テーマ別スコア
  - 銘柄別スコア
  - `overall_action` の決定

watchlist の主な出力:

- `themes`
- `tickers`
- `overall_action`

### 3. Analysis

- [engine/analyzer.py](/C:/AI/Share/youtube_patrol_v2/engine/analyzer.py)
  - Gemini による sentiment / council 判断
  - `market / news / youtube / watchlist / confirmed_watch_tickers / portfolio` をまとめて文脈化

### 4. Execution

- [engine/broker.py](/C:/AI/Share/youtube_patrol_v2/engine/broker.py)
  - 模擬ポートフォリオ管理
  - IFDOCO 連携

### 5. Persistence / Reporting

- [engine/patrol_store.py](/C:/AI/Share/youtube_patrol_v2/engine/patrol_store.py)
  - snapshot 保存
  - report 保存
  - watchlist 保存
  - Discord 通知

- [engine/external_store.py](/C:/AI/Share/youtube_patrol_v2/engine/external_store.py)
  - 任意の外部ストレージ保存

## ジョブ構成

### main patrol

- [engine/main.py](/C:/AI/Share/youtube_patrol_v2/engine/main.py)
- 市場・ニュース中心
- 最新 watchlist を読み込む
- `WATCH` 銘柄のうち、価格確認が取れたものを `confirmed_watch_tickers` として扱う
- council に watchlist 情報を渡す

### youtube patrol

- [engine/youtube_job.py](/C:/AI/Share/youtube_patrol_v2/engine/youtube_job.py)
- YouTube 巡回
- watchlist 生成
- YouTube 用 Discord 通知

## 設定

[infra/config/app_config.json](/C:/AI/Share/youtube_patrol_v2/infra/config/app_config.json) に主な設定があります。

- `target_tickers`
- `news_feeds`
- `youtube_patrol_targets`
- `youtube_max_videos`
- `theme_ticker_map`
- `watchlist_rules`
- `risk`

`theme_ticker_map` により、YouTube のテーマを日本株の候補銘柄へ変換します。

## 出力

### main patrol

- `data/patrol/latest_snapshot.json`
- `data/patrol/latest_report.md`

### youtube patrol

- `data/youtube_patrol/latest_snapshot.json`
- `data/youtube_patrol/latest_report.md`
- `data/youtube_patrol/latest_watchlist.json`
- `data/youtube_patrol/watchlist_report.md`

## 通知設計

### YouTube 通知

含めるもの:

- `Action`
- `Themes`
- `Candidates`
- `Video`
- `Trading note`

### main 通知

含めるもの:

- `Action`
- `Summary`
- `News`
- `Decision`
- `Trading note`

## 現在の制約

1. YouTube のローカル同期実行は重い
GitHub Actions では安定動作を優先し、ローカル同期では待機が長くなることがあります。

2. YouTube 単独では `BUY` を出さない
現在は `WATCH / AVOID / NO SIGNAL` を中心に返します。

3. watchlist は前段エンジン
価格ブレイク、ニュース追認、リスク条件のような後段ロジックは別に見る設計です。
