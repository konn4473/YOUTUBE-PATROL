# Next Steps

最終更新: 2026-03-25

## 今すぐ必須ではないもの

現時点では、push 前に追加しなければならない必須作業はありません。

## 次にやる候補

### 優先度: 中

#### 1. GitHub Actions の最新通し確認

目的:

- 軽量モード、watchlist 変化通知、段階別シグナル表示が GitHub 上で崩れないか確認する
- `responseSchema` 付き Gemini 呼び出しが Actions 上でも問題ないか確認する
- stale watchlist ガードが想定どおり動くか確認する

#### 2. Discord の最終表示確認

目的:

- 日本語通知が実運用で読みやすいか確認する
- `固定チャンネル / 検索` の内訳が伝わるか確認する
- `AI提案 / 候補絞り込み / 最終判断` の差分が長すぎず読めるか確認する
- `AI状態 / cooldown / watchlist状態変化 / watchlist候補変化` が長すぎず読めるか確認する
- `設定変化 / AI request config / AIリクエスト設定変化` が長すぎず読めるか確認する
- 通知が長すぎないか確認する

#### 3. 固定チャンネル由来の寄与観察

目的:

- しばらく回して、固定チャンネル由来の候補が増えるかを見る
- 候補銘柄の `fixed / search` 比率が偏りすぎていないかを見る

#### 4. AI 紙上売買の成績確認

目的:

- `data/paper_ai_history.json` と `data/paper_ai_summary.json` を見て、
  proposal と final の差を見ながら勝率と損益を確認する
- 保有日数が長すぎないかを見る

#### 5. レポート実データ確認

目的:

- `data/patrol/latest_report.md` に段階差分が期待どおり出るか確認する
- `watchlist状態 / watchlist候補変化` と `AI runtime / cooldown` が追いやすいか確認する
- `Runtime Config` と `AI request config` が追いやすいか確認する
- `data/patrol/latest_snapshot.json` の `decisions` 差分を数 run 分見て妥当性を確認する

### 優先度: 低

#### 6. YouTube 実行のさらなる軽量化

目的:

- 実行時間を短くする
- quota 超過日の影響を減らす

現状:

- `youtube_max_videos = 1`
- `max_items = 20`
  まで軽量化済み
- 感情分析は直列化と件数上限制御を追加済み

#### 7. 監視対象の見直し

目的:

- 数週間運用して偏りが見えたら調整する
- 現時点では増やしすぎない

## 今はやらないこと

- 本番の完全自動売買
- 監視対象の無制限な追加
- VPS への即時移行

これらは、現段階では不要です。
