# Project Status

最終更新: 2026-03-19

## 目的
`youtube_patrol_v2` は、YouTube とニュースを使って監視候補を抽出し、価格確認を通したうえで売買判断の材料を作る巡回システムです。

## いまできること

- YouTube から動画候補を集める
- テーマを抽出する
- 候補銘柄を watchlist 化する
- `BUY / WATCH / AVOID / NO SIGNAL` の行動ラベルを出す
- ニュースと価格で裏取りする
- AI 提案を出す
- AI 提案の紙上売買を記録し、仮想損益を集計する
- Gemini が使えない日でも YouTube 巡回を軽量モードで継続する
- fixed / search の寄与を watchlist と通知で見分ける
- YouTube の感情分析は順番に流し、1回の巡回で使う回数に上限を持たせる
- GitHub Actions で毎朝 7:30 JST に実行する
- Discord に通知する
- Gemini の呼び出し量を抑える軽量設定で運用する

## 現在の運用フロー

1. YouTube の固定チャンネルと検索結果を収集する
2. テーマと候補銘柄を watchlist にまとめる
3. AI が候補を提案する
4. ニュースと価格で裏取りする
5. council が最終判断する
6. AI 提案は紙上売買にも記録し、損益を追跡する
7. `AVOID` は AI 提案と最終判断の両方で安全側に反映する

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

### 現在の軽量設定

- `youtube_max_videos = 1`
- `youtube_patrol_targets.max_items = 20`
- Gemini retry は GitHub Actions で最小化済み

## 保存ファイル

### main patrol

- `data/patrol/latest_report.md`
- `data/patrol/latest_snapshot.json`
- `data/patrol/history/...`

### youtube patrol

- `data/youtube_patrol/latest_report.md`
- `data/youtube_patrol/latest_snapshot.json`
- `data/youtube_patrol/latest_watchlist.json`
- `data/youtube_patrol/watchlist_report.md`

### 紙上売買

- `data/paper_ai_positions.json`
- `data/paper_ai_history.json`
- `data/paper_ai_signals.json`
- `data/paper_ai_summary.json`

## 現在わかっていること

- GitHub Actions では完走できている
- 実行時間と quota を見て、YouTube 処理量は少し抑えた
- 実行時間はやや長めなので、今後も監視は必要
- Gemini の quota によっては日によって応答が重くなる
- Gemini 2.5 Flash Lite を感情分析に使い、RPM 超過を抑える
- watchlist はまだ検索由来が強く、固定チャンネル由来は観察中
- YouTube 通知は watchlist 行動や上位候補の変化でも飛ぶ
- main 通知は confirmed watch、AI提案、候補絞り込みの差分を出す
- 紙上売買では保有日数と最近のシグナル行動まで追跡できる

## 直近の評価

- 監視対象は現時点では増やしすぎない方がよい
- YouTube は直接売買判断ではなく、候補抽出に使う方が安全
- AI は本番自動売買ではなく、まず提案と紙上売買で検証する
- 固定チャンネル寄与は増やすより先に見える化して観察する
