# GitHub Actions Guide

## 概要

このプロジェクトは GitHub Actions で毎朝 `07:30 JST` に実行できます。
ワークフローは [morning-patrol.yml](/C:/AI/Share/youtube_patrol_v2/.github/workflows/morning-patrol.yml) です。

実行内容:

1. `infra/.env` を GitHub Secrets から生成
2. `main patrol` を実行
3. `youtube patrol` を実行
4. `data/patrol` と `data/youtube_patrol` を artifact として保存

## 実行時刻

- GitHub Actions の cron は UTC
- `07:30 JST` は前日 `22:30 UTC`
- 現在の cron:

```text
30 22 * * *
```

## 必要な Secrets

リポジトリの `Settings > Secrets and variables > Actions` に次を登録します。

- `GOOGLE_API_KEY`
- `GEMINI_API_KEY`
- `DISCORD_WEBHOOK_URL`

補足:

- `GOOGLE_API_KEY` と `GEMINI_API_KEY` は同じ Gemini キーでも動きます
- `DISCORD_WEBHOOK_URL` が未設定でも workflow 自体は動きます

## 実行後に残るもの

artifact に以下が入ります。

- `data/patrol`
- `data/youtube_patrol`

主な確認対象:

- `latest_report.md`
- `latest_snapshot.json`
- `latest_watchlist.json`
- `watchlist_report.md`

## Discord 通知

現在の Discord 通知は watchlist ベースです。

YouTube 通知には次が含まれます。

- `Action`
- `Themes`
- `Candidates`
- `Video`
- `Trading note`

`main patrol` 通知には次が含まれます。

- `Action`
- `Summary`
- `News`
- `Decision`
- `Trading note`

## 注意点

1. GitHub Actions runner は毎回クリーンな環境です
永続的なローカル履歴は保持されません。各回の成果物は artifact で確認します。

2. YouTube ジョブはローカルより GitHub Actions の方が安定しています
ローカルの同期実行では待機上限に掛かることがあります。

3. YouTube 通知は売買シグナルではありません
`YouTube alone is not a buy signal.` の方針です。

## 手動実行

GitHub の `Actions` タブから `Morning Patrol` を選び、`Run workflow` で手動実行できます。

## トラブル時の見方

失敗した場合は step ごとにログを見ます。

見る順番:

1. `Prepare env file`
2. `Run main patrol`
3. `Run youtube patrol`
4. `Upload patrol artifacts`

`Permission denied: data/patrol` が出る場合は、workflow が古い commit の再実行になっていないか確認してください。
修正版では `docker compose run --rm --user root ...` で実行します。
