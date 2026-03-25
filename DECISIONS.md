# Decisions

最終更新: 2026-03-25

## 主要な決定事項

### 1. YouTube は直接の買いシグナルにしない

- YouTube 単独で `BUY` を出さない
- まず watchlist を作る
- その後にニュースと価格で裏取りする

### 2. 判断フローは固定する

1. YouTube 収集
2. 候補銘柄化
3. AI 提案
4. 別データ確認
5. 最終判断

### 3. `BUY` は価格確認が通ったものだけ

- watchlist 銘柄は価格確認が通るまで `WATCH`
- 条件不足の AI 提案も `WATCH` に落とす

### 4. 固定チャンネルと検索を併用する

- 固定チャンネルは基準点
- 検索は話題の補完
- どちら由来かは Discord とレポートで見えるようにする

### 5. Discord には行動ラベルを出す

- `買い`
- `売り`
- `監視`
- `見送り`
- `シグナルなし`

### 6. 通知は日本語で読む

- Discord 通知は日本語を基本にする
- テーマ、候補銘柄、補足を日本語で出す

### 7. AI は提案役に留める

- いきなり本番自動売買には使わない
- まずは提案と紙上売買で精度を見る

### 8. 紙上売買で AI 提案を検証する

- AI 提案と shortlist を毎回記録する
- 最終判断も別段階として記録する
- 仮想ポジションの損益を自動集計する
- proposal と final は分けて見られるようにする
- これを本番自動売買前の検証材料にする

### 9. 実行基盤は当面 GitHub Actions を使う

- まずは GitHub Actions で安定運用する
- VPS や self-hosted runner は必要になってから検討する

### 10. Gemini は少額有料を許容しても、先に軽量化する

- いきなり件数を増やして課金に頼らない
- まず YouTube 処理量を抑える
- そのうえで少額有料で安定運用する

### 11. Gemini が使えない日でも巡回は止めない

- API 無効や cooldown でも収集と watchlist 作成は続ける
- その日は軽量モードで動かし、精度低下は許容する

### 12. `AVOID` は安全側に強く反映する

- watchlist が `AVOID` の銘柄は AI 提案の `BUY` をそのまま通さない
- council の `BUY` も `AVOID` に落として扱う

### 13. 通知は新着件数だけでなく質的変化も見る

- watchlist 行動の変化
- 上位候補銘柄の変化
- confirmed watch や shortlist の変化
を Discord 通知の条件に使う

### 14. Gemini の無料枠は RPM 超過を避ける設計にする

- YouTube の感情分析は同時並列で投げすぎない
- 1回の巡回で使う感情分析回数に上限を持たせる
- それを超えた分は軽量な `0.0` 応答で継続する
- 感情分析モデルは安定運用を優先して `Gemini 2.5 Flash Lite` を使う

### 15. 同一 workflow の main は最新の YouTube watchlist を使う

- GitHub Actions では `youtube patrol` を `main patrol` より先に実行する
- 同じ run で更新された `latest_watchlist.json` を `main patrol` が読む
- 同じ branch の重複実行は `concurrency` で抑止する
- 古すぎる watchlist は `main patrol` で使わず、安全側に倒す

### 16. Gemini の AI 出力は schema 付き JSON を基本にする

- prompt のお願いだけに頼らず、API の `responseSchema` も使う
- それでも壊れる場合に備えて後段の normalize は残す
- 最小変更で壊れにくさを上げる

### 17. 運用の切り分けに必要な状態は report と通知へ残す

- `watchlist` の fresh / stale 状態を残す
- `watchlist` の上位候補の変化も残す
- AI の live / mock、model、cooldown 状態を残す
- 主要設定と AI request config も report に残す
- AI request config の変化は通知でも追えるようにする
- 変化があった日は差分として追えるようにする
