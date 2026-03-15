# Docker 運用ガイド (Codex/開発担当向け)

このプロジェクトは Docker コンテナ内での実行を前提に提供されています。開発および検証は以下の手順で行ってください。

## 1. 準備
`infra/.env` を作成し、必要な API キーを設定してください。
```bash
cp infra/.env.template infra/.env
# Gemini API Key などを追記
```

## 2. ビルド
環境を構築します。
```bash
docker-compose build
```

## 3. 実行

### メインシステムの起動
```bash
docker-compose up app
```

### シミュレーション（検証）の実行
```bash
docker-compose run --rm sim
```

## 4. 開発時の注意点
- ホスト側のファイル（`engine/` など）を変更すると、コンテナ内にも即座に反映されます。
- ライブラリを新規追加した場合は、`requirements.txt` を更新した後に `docker-compose build` を再度実行してください。
- ログや取引データはホスト側の `data/` フォルダに永続化されます。
