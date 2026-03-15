# Python 3.11 slim 版をベースに使用
FROM python:3.11-slim

# システムパッケージのインストール（YouTube解析や一部ライブラリのビルドに必要）
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    git \
    build-essential \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# 作業ディレクトリの設定
WORKDIR /app

# 依存ファイルのコピーとインストール
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# アプリケーションコードのコピー
COPY . .

# 実行ユーザーを non-root に設定（セキュリティ推奨）
RUN useradd -m appuser && chown -R appuser /app
USER appuser

# メインスクリプトをデフォルトの実行対象に設定
CMD ["python", "engine/main.py"]
