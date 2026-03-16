# GitHub Actions Guide

## 概要
このプロジェクトは GitHub Actions で毎朝 `07:30 JST` に自動実行できます。
ワークフロー本体は [morning-patrol.yml](/C:/AI/Share/youtube_patrol_v2/.github/workflows/morning-patrol.yml) です。

処理の流れは次です。

1. `infra/.env` を GitHub Secrets から作成
2. `main patrol` を実行
3. `youtube patrol` を実行
4. `data/patrol` と `data/youtube_patrol` を artifact として保存

## 実行時刻

- GitHub Actions の cron は UTC 基準です
- `07:30 JST` は `22:30 UTC` です
- cron は次です

```text
30 22 * * *
```

## 必要な Secrets

リポジトリの `Settings > Secrets and variables > Actions` で次を登録します。

- `GOOGLE_API_KEY`
- `GEMINI_API_KEY`
- `DISCORD_WEBHOOK_URL`

補足:

- `GOOGLE_API_KEY` と `GEMINI_API_KEY` は同じ Gemini キーでも動きます
- `DISCORD_WEBHOOK_URL` が未設定なら、通知だけスキップされます

## artifact に保存されるもの

artifact の中には次が入ります。

- `data/patrol`
- `data/youtube_patrol`

主な確認対象:

- `latest_report.md`
- `latest_snapshot.json`
- `latest_watchlist.json`
- `watchlist_report.md`

## Discord 通知

### YouTube 通知

YouTube 通知では次が分かります。

- `Action`
- `Themes`
- `Candidates`
- `Video`
- `Trading note`

YouTube 単独で売買しない前提なので、通知文にも `YouTube alone is not a buy signal.` を入れています。

### main patrol 通知

`main patrol` 通知では次が分かります。

- `Action`
- `Summary`
- `News`
- `Decision`
- `Trading note`

## 最近の改善点

- `docker compose run --rm --user root ...` で GitHub Actions 上の書き込み権限問題を回避
- `actions/checkout@v6` と `actions/upload-artifact@v6` を使用
- artifact 保持期間を 14 日に設定
- YouTube は直近 `recent_hours` 時間だけを対象にする
- `parallel_workers` で YouTube 解析を並列化
- `use_transcripts=false` でローカルの重さを抑えやすくする
- watchlist 銘柄は価格確認が取れるまで `buy` にしない設定に対応
- 任意で外部ストレージへアップロードできる

## 外部ストレージ保存

次の環境変数を設定すると、生成物を S3 互換ストレージへアップロードできます。

- `S3_BUCKET`
- `S3_ENDPOINT_URL`
- `AWS_REGION`
- `S3_PREFIX`

未設定ならアップロードは行いません。

## 手動実行

GitHub の `Actions` タブから `Morning Patrol` を選び、`Run workflow` で手動実行できます。

## トラブル時の見方

失敗した場合は、次の step を順に確認します。

1. `Prepare env file`
2. `Run main patrol`
3. `Run youtube patrol`
4. `Upload patrol artifacts`

過去に `Permission denied: data/patrol` が出たことがありましたが、現在は `--user root` 付きの実行に修正済みです。
