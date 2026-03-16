# YouTube Patrol v2.0

## 概要
`youtube_patrol_v2` は、日本株・ニュース・YouTube を巡回して、監視候補をまとめるバッチ型の監視システムです。

今の設計では、YouTube は「売買を直接決める場所」ではなく、「監視候補を見つける場所」として使います。
そのため、YouTube だけで `BUY` は出さず、次のような形で使います。

- テーマ抽出
- 候補銘柄抽出
- `WATCH / AVOID / NO SIGNAL`
- 補助的な通知

最終的な売買判断は、価格・ニュース・ポートフォリオ状況を含めた `main patrol` 側で行います。

## 現在の構成

- [engine/collector.py](/C:/AI/Share/youtube_patrol_v2/engine/collector.py)
  - 市場データと RSS ニュースの取得
- [engine/youtube_analyzer.py](/C:/AI/Share/youtube_patrol_v2/engine/youtube_analyzer.py)
  - YouTube 動画の収集、感情分析、テーマ抽出、候補銘柄抽出
- [engine/watchlist_builder.py](/C:/AI/Share/youtube_patrol_v2/engine/watchlist_builder.py)
  - YouTube 結果から watchlist を生成
- [engine/analyzer.py](/C:/AI/Share/youtube_patrol_v2/engine/analyzer.py)
  - Gemini を使った sentiment / council 判断
- [engine/main.py](/C:/AI/Share/youtube_patrol_v2/engine/main.py)
  - 市場・ニュース中心の本体ジョブ
- [engine/youtube_job.py](/C:/AI/Share/youtube_patrol_v2/engine/youtube_job.py)
  - YouTube 巡回専用ジョブ
- [engine/patrol_store.py](/C:/AI/Share/youtube_patrol_v2/engine/patrol_store.py)
  - レポート、スナップショット、watchlist、Discord 通知の保存
- [engine/external_store.py](/C:/AI/Share/youtube_patrol_v2/engine/external_store.py)
  - 任意の外部ストレージアップロード
- [engine/broker.py](/C:/AI/Share/youtube_patrol_v2/engine/broker.py)
  - 模擬ポートフォリオと IFDOCO 連携

## 出力先

市場・ニュース巡回:

- [data/patrol/latest_report.md](/C:/AI/Share/youtube_patrol_v2/data/patrol/latest_report.md)
- [data/patrol/latest_snapshot.json](/C:/AI/Share/youtube_patrol_v2/data/patrol/latest_snapshot.json)

YouTube 巡回:

- [data/youtube_patrol/latest_report.md](/C:/AI/Share/youtube_patrol_v2/data/youtube_patrol/latest_report.md)
- [data/youtube_patrol/latest_snapshot.json](/C:/AI/Share/youtube_patrol_v2/data/youtube_patrol/latest_snapshot.json)
- [data/youtube_patrol/latest_watchlist.json](/C:/AI/Share/youtube_patrol_v2/data/youtube_patrol/latest_watchlist.json)
- [data/youtube_patrol/watchlist_report.md](/C:/AI/Share/youtube_patrol_v2/data/youtube_patrol/watchlist_report.md)

## 通知の見方

Discord 通知では、最低限次が分かるようにしています。

- `Action`
- `Themes`
- `Candidates`
- `Decision`
- `Trading note`

YouTube 通知では、YouTube 単独で売買しない前提なので、`YouTube alone is not a buy signal.` を明示しています。

## 主な設定

主な設定は [infra/config/app_config.json](/C:/AI/Share/youtube_patrol_v2/infra/config/app_config.json) にあります。

- `target_tickers`
- `news_feeds`
- `youtube_patrol_targets`
- `youtube_max_videos`
- `theme_ticker_map`
- `watchlist_rules`
- `enable_youtube_analysis`
- `enable_youtube_job`

### 最近入れた改善

- YouTube は `recent_hours` で直近動画だけを対象にする
- `parallel_workers` で YouTube 解析を並列化する
- `use_transcripts` を `false` にすると、ローカルでの重さを抑えられる
- `buy_requires_price_confirmation` が有効な場合、watchlist 銘柄は価格確認が取れるまで `buy` にしない
- `S3_BUCKET` などを設定すると、生成物を外部ストレージへアップロードできる

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
docker-compose run --rm sim python sims/test_main_helpers.py
```

補足:

- `youtube` は外部取得が重いため、ローカルの同期実行では待機時間が長くなることがあります
- GitHub Actions 側では定期実行前提で安定して動く構成にしています

## GitHub Actions

定期実行ワークフローは [morning-patrol.yml](/C:/AI/Share/youtube_patrol_v2/.github/workflows/morning-patrol.yml) です。

- 毎日 `07:30 JST`
- `app` と `youtube` を順に実行
- `data/patrol` と `data/youtube_patrol` を artifact 保存

詳しくは [docs/github_actions_guide.md](/C:/AI/Share/youtube_patrol_v2/docs/github_actions_guide.md) にまとめています。

## 運用の考え方

このプロジェクトは「いきなり買う bot」ではなく、「監視候補を見つけて、次の判断材料に渡す bot」として設計しています。

運用の基本は次です。

- YouTube: テーマと watchlist を作る
- ニュース・価格: 追認に使う
- council: 最終判断を返す

そのため、YouTube の多数決だけで買うのではなく、watchlist 上位銘柄を後段で再評価する形を取っています。
