# YouTube Patrol v2.0

## 概要

`youtube_patrol_v2` は、日本株・ニュース・YouTube 動画を巡回し、毎朝の監視候補をまとめるバッチ型の巡回システムです。

現在の YouTube 部分は「売買判断エンジン」ではなく、「監視候補抽出エンジン」として動きます。
YouTube から直接 `BUY` を出すのではなく、次を出力します。

- テーマ
- 候補銘柄
- `WATCH / AVOID / NO SIGNAL`
- 補足理由

実際の売買判断は、価格・ニュース・ポートフォリオ情報を加えた `main` 側で行います。

## 現在の構成

- [engine/collector.py](/C:/AI/Share/youtube_patrol_v2/engine/collector.py)
  - 市場データと RSS ニュースの取得
- [engine/youtube_analyzer.py](/C:/AI/Share/youtube_patrol_v2/engine/youtube_analyzer.py)
  - YouTube 動画の収集、字幕取得、感情分析、テーマ抽出、候補銘柄抽出
- [engine/watchlist_builder.py](/C:/AI/Share/youtube_patrol_v2/engine/watchlist_builder.py)
  - YouTube 結果から watchlist を集計
- [engine/analyzer.py](/C:/AI/Share/youtube_patrol_v2/engine/analyzer.py)
  - Gemini を使った sentiment と council 判断
- [engine/main.py](/C:/AI/Share/youtube_patrol_v2/engine/main.py)
  - 市場・ニュース中心の本体ジョブ
- [engine/youtube_job.py](/C:/AI/Share/youtube_patrol_v2/engine/youtube_job.py)
  - YouTube 専用ジョブ
- [engine/patrol_store.py](/C:/AI/Share/youtube_patrol_v2/engine/patrol_store.py)
  - レポート、スナップショット、watchlist、Discord 通知の保存
- [engine/broker.py](/C:/AI/Share/youtube_patrol_v2/engine/broker.py)
  - 仮想ポートフォリオと IFDOCO 監視

## 出力物

市場・ニュース巡回:

- [data/patrol/latest_report.md](/C:/AI/Share/youtube_patrol_v2/data/patrol/latest_report.md)
- [data/patrol/latest_snapshot.json](/C:/AI/Share/youtube_patrol_v2/data/patrol/latest_snapshot.json)

YouTube 巡回:

- [data/youtube_patrol/latest_report.md](/C:/AI/Share/youtube_patrol_v2/data/youtube_patrol/latest_report.md)
- [data/youtube_patrol/latest_snapshot.json](/C:/AI/Share/youtube_patrol_v2/data/youtube_patrol/latest_snapshot.json)
- [data/youtube_patrol/latest_watchlist.json](/C:/AI/Share/youtube_patrol_v2/data/youtube_patrol/latest_watchlist.json)
- [data/youtube_patrol/watchlist_report.md](/C:/AI/Share/youtube_patrol_v2/data/youtube_patrol/watchlist_report.md)

## 通知方針

Discord 通知は、次が分かる形にしています。

- `Action`
- `Themes`
- `Candidates`
- `Decision`

YouTube 通知は補助シグナルです。通知にも `YouTube alone is not a buy signal.` を明記しています。

## 設定

主要設定は [infra/config/app_config.json](/C:/AI/Share/youtube_patrol_v2/infra/config/app_config.json) にあります。

主な項目:

- `target_tickers`
- `news_feeds`
- `youtube_patrol_targets`
- `youtube_max_videos`
- `theme_ticker_map`
- `enable_youtube_analysis`
- `enable_youtube_job`

## ローカル実行

本体ジョブ:

```powershell
docker-compose run --rm app python -u engine/main.py
```

YouTube ジョブ:

```powershell
docker-compose run --rm youtube python -u engine/youtube_job.py
```

テスト:

```powershell
docker-compose run --rm sim python sims/test_v2_core.py
docker-compose run --rm sim python sims/test_patrol_store.py
docker-compose run --rm sim python sims/test_watchlist_builder.py
```

補足:

- `youtube` は外部取得が重いため、ローカルの同期実行では待機上限に掛かることがあります
- GitHub Actions 側では完走確認済みです

## GitHub Actions

定期実行ワークフローは [morning-patrol.yml](/C:/AI/Share/youtube_patrol_v2/.github/workflows/morning-patrol.yml) です。

- 毎日 `07:30 JST`
- `app` と `youtube` を順に実行
- `data/patrol` と `data/youtube_patrol` を artifact 保存

詳細は [docs/github_actions_guide.md](/C:/AI/Share/youtube_patrol_v2/docs/github_actions_guide.md) を参照してください。

## 現在の判断

このプロジェクトは「最低限動く巡回 bot」の段階を超えて、監視候補抽出まで実装済みです。
一方で、YouTube 単独での売買判断は採用していません。

実務的な位置付けは次です。

- YouTube: テーマ検出と watchlist 生成
- ニュースと価格: 裏付け確認
- council: 最終判断
