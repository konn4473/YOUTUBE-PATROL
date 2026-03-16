# Project Status

最終更新: 2026-03-16

## 現在の目的

`youtube_patrol_v2` は、YouTube・ニュース・市場データを使って監視候補を抽出し、最終的な売買判断の前段を支える監視システムです。

## 今できること

- YouTube から動画候補を収集する
- テーマを抽出する
- 候補銘柄を watchlist 化する
- AI が候補銘柄を提案する
- 価格確認ルールで `BUY` を `WATCH` に落とす
- `main patrol` と `youtube patrol` を分離して実行する
- GitHub Actions で毎朝実行する
- Discord に `Action` 付きで通知する

## 現在の運用フロー

1. YouTube の多数決で話題を拾う
2. watchlist を作る
3. AI が候補を提案する
4. ニュースと価格で確認する
5. council が最終判断する

## 現在の監視対象

### 市場データ

- `6501`
- `7203`
- `8035`
- `BTC-JPY`

### ニュース

- Reuters
- Nikkei
- Bloomberg

### 固定 YouTube チャンネル

- TV Tokyo News
- TBS NEWS DIG
- 日経CNBC
- テレ東BIZ
- トウシル
- 日テレNEWS
- FNNプライムオンライン
- PIVOT 公式チャンネル
- SBI証券公式 ビジネスドライブ！
- カブりつき・マーケット情報局

### YouTube 検索キーワード

- 日本株
- 日経平均
- 半導体株
- 防衛関連
- 商社株
- 銀行株
- 原油 日本株
- 円安 日本株

## 現在の保存先

### main patrol

- `data/patrol/latest_report.md`
- `data/patrol/latest_snapshot.json`

### youtube patrol

- `data/youtube_patrol/latest_report.md`
- `data/youtube_patrol/latest_snapshot.json`
- `data/youtube_patrol/latest_watchlist.json`
- `data/youtube_patrol/watchlist_report.md`

## 現在分かっていること

- ローカルの `youtube` 同期実行は重く、待機上限にかかることがある
- ただし出力ファイルは更新されるため、処理自体は進んでいる
- 直近の watchlist は検索由来が強く、固定チャンネル由来はまだ弱い

## 直近の注目点

- Discord とレポートで `fixed / search` の比率が見えるようになった
- AI 提案は `NO SIGNAL` の日は無理に出さない
- 固定チャンネルは 10 件まで拡張済み
