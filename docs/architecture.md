# YouTube Patrol v2.0 アーキテクチャ

## 目的

YouTube、ニュース、価格データを組み合わせて、毎朝の監視候補を作る巡回システムを構築することです。

現時点での方針は次です。

- YouTube は監視候補抽出に使う
- ニュースと価格で裏付けを取る
- 最終判断は council に寄せる

YouTube 単独での自動売買は行いません。

## レイヤ構成

### 1. Collection

- [engine/collector.py](/C:/AI/Share/youtube_patrol_v2/engine/collector.py)
  - 市場データ
  - RSS ニュース

- [engine/youtube_analyzer.py](/C:/AI/Share/youtube_patrol_v2/engine/youtube_analyzer.py)
  - チャンネル・検索キーワードから動画収集
  - 字幕取得
  - テーマ抽出
  - 候補銘柄抽出

### 2. Watchlist

- [engine/watchlist_builder.py](/C:/AI/Share/youtube_patrol_v2/engine/watchlist_builder.py)
  - 動画単位の結果を集約
  - テーマ別スコア
  - 銘柄別スコア
  - `overall_action` 算出

この層の出力は:

- `themes`
- `tickers`
- `overall_action`

### 3. Analysis

- [engine/analyzer.py](/C:/AI/Share/youtube_patrol_v2/engine/analyzer.py)
  - Gemini による sentiment 分析
  - market/news/youtube/watchlist/portfolio を使った council 判断

### 4. Execution

- [engine/broker.py](/C:/AI/Share/youtube_patrol_v2/engine/broker.py)
  - 仮想ポートフォリオ管理
  - IFDOCO 監視

### 5. Persistence / Reporting

- [engine/patrol_store.py](/C:/AI/Share/youtube_patrol_v2/engine/patrol_store.py)
  - snapshot 保存
  - report 保存
  - watchlist 保存
  - Discord 通知

## ジョブ分割

### main patrol

- [engine/main.py](/C:/AI/Share/youtube_patrol_v2/engine/main.py)
- 市場・ニュース中心
- 最新 watchlist を読み込み
- council に watchlist 文脈を渡す

### youtube patrol

- [engine/youtube_job.py](/C:/AI/Share/youtube_patrol_v2/engine/youtube_job.py)
- YouTube 専用
- watchlist を生成
- YouTube 用 Discord 通知を送る

## 設定

[infra/config/app_config.json](/C:/AI/Share/youtube_patrol_v2/infra/config/app_config.json) に以下を持ちます。

- `target_tickers`
- `news_feeds`
- `youtube_patrol_targets`
- `youtube_max_videos`
- `theme_ticker_map`
- `risk`

`theme_ticker_map` により、YouTube のテーマを日本株銘柄へ変換します。

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

1. YouTube のローカル同期実行は遅い
GitHub Actions では完走確認済みです。

2. YouTube 単独では `BUY` を出さない
現状は `WATCH / AVOID / NO SIGNAL` を中心に扱います。

3. watchlist は最初の実装段階
将来的には複数動画の時系列集計や価格条件連携を強める余地があります。
