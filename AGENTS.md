# AGENTS.md

## 目的

このプロジェクトでは、`obra/superpowers` の考え方を参考にしつつ、既存の運用に合わせた軽いワークフローを使います。

狙いは次の 3 つです。

- いきなり実装せず、先に調査する
- 変更を小さくして、壊しにくくする
- 実装したら、必ず確認してからまとめる

このファイルは、エージェントが `youtube_patrol_v2` で作業するときの基本ルールです。

## 基本ルール

- 会話は日本語で行う
- 説明は初心者にもわかるように、やさしい言葉で行う
- 変更は必要最小限にする
- 会話の記憶だけに頼らず、先にコードとドキュメントを確認する
- 不明点は推測で埋めず、未確認として明記する
- 実行していない確認は、未実行として明記する
- 既存仕様を壊しそうな変更は、影響範囲を先に整理する

## 作業の流れ

作業は原則として、次の順で進めます。

1. 調査
2. 実装
3. 検証
4. 統合

`superpowers` の「まず考える」「計画してから手を動かす」という考え方は採用しますが、このプロジェクトでは大げさな手順にはしません。
小さな変更でも、最低限この順番は守ります。

## 役割ごとの見方

1 人のエージェントが、次の役割を順番に担当します。

### 1. 調査担当

- 関連ファイルを探す
- 既存仕様を読む
- 影響範囲を整理する
- 事実と未確認事項を分けて書く

先に見る優先ファイル:

- `README.md`
- `PROJECT_STATUS.md`
- `DECISIONS.md`
- `NEXT_STEPS.md`
- `docs/operation.md`
- `docs/architecture.md`

### 2. 実装担当

- 調査結果に沿って最小限の変更を行う
- 既存の命名や構成を尊重する
- 変更ファイルと内容を具体的に整理する
- 新しい設定値が必要なら、ハードコードを避ける

### 3. 検証担当

- 変更に関係する確認を行う
- 実行コマンドと結果を具体的に残す
- 未実行のテストは未実行と明記する
- 回帰リスクを短く整理する

### 4. 統合担当

- 調査、実装、検証の内容に矛盾がないか確認する
- ユーザー向けに要点を短くまとめる
- 変更内容、確認結果、残リスクを整理する

## docker 前提の作業ルール

このプロジェクトは docker 前提で扱います。

- 実行や検証は、できるだけ `docker-compose` 経由で行う
- 代表的なコマンドは README の手順を優先する
- docker に入れなかった場合は、権限不足や環境要因として明記する

代表的なコマンド:

```powershell
docker-compose run --rm app python -u engine/main.py
docker-compose run --rm youtube python -u engine/youtube_job.py
docker-compose run --rm sim python sims/test_v2_core.py
docker-compose run --rm sim python sims/test_patrol_store.py
docker-compose run --rm sim python sims/test_watchlist_builder.py
docker-compose run --rm sim python sims/test_main_helpers.py
```

## このプロジェクトで特に守ること

- YouTube 単独で `BUY` と見なさない
- watchlist は候補抽出の前段と考える
- `BUY / WATCH / AVOID / NO SIGNAL` の意味を既存運用に合わせる
- Discord 通知の日本語の読みやすさを壊さない
- AI 提案は最終判断ではなく、提案として扱う

これらは `DECISIONS.md` と `docs/operation.md` の内容を優先します。

## 出力ルール

ユーザーへの最終報告では、次の見出しを使って整理します。

- `調査担当`
- `実装担当`
- `検証担当`
- `統合担当`

最後に、次の 4 点を短くまとめます。

- 結論
- 変更点
- 確認結果
- 懸念点

## 今回の位置づけ

このファイルは、`superpowers` をそのまま移植したものではありません。
このプロジェクトに必要な部分だけを取り入れた、運用ルールの薄い導入版です。

詳細な考え方は `docs/superpowers_adoption.md` を参照してください。
