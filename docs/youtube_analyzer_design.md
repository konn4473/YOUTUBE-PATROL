# YouTube Analyzer 詳細設計

## 1. 目的
YouTube動画の「主観」情報（インフルエンサーの期待感やニュースの論調）を抽出・数値化し、投資判断委員会（Council）に提供する。

## 2. 処理フロー
1.  **URL取得**: `YouTube Collector` が `app_config.json` に基づき最新動画URLを抽出。
2.  **テロップ・字幕抽出**:
    *   `youtube-transcript-api` を使用して日本語字幕（自動生成含む）を取得。
    *   取得失敗時は `yt-dlp` でメタデータ（タイトル・説明文）を代替。
3.  **要約 & センチメント分析 (Gemini 1.5 Flash)**:
    *   **Input**: 動画タイトル、説明文、字幕テキスト。
    *   **Prompt**: 「この動画の市場に対するセンチメントを -1.0 (強気) ～ 1.0 (弱気) で判定し、理由を3行で要約してください。」
    *   **Output**: JSON形式（sentiment, summary, keywords）。
4.  **提供**: 分析結果を `engine/analyzer.py` の辞書形式で `Investment Council` に送出。

## 3. 採用技術
*   処理系: `youtube-transcript-api` (軽量・高速)
*   フォールバック: `yt-dlp` (メタデータ取得用)
*   AIモデル: `Gemini 1.5 Flash` (低価格・高スピード・ロングコンテキスト対応)

## 4. 課題・懸念点
*   字幕が完全に無効な動画への対応（現在は説明文で代用設計）。
*   APIキーの制限。
