# 開発ガイド

## ブランチとコミット
- メイン開発は `main` を既定とし、機能ごとにブランチを切って PR
- コミットは意味のある最小単位で。推奨: Conventional Commits（例: `feat: add stock search`）

## Python 側
- 実行: `uv run uvicorn app.main:app --reload`
- テスト: `PYTHONPATH=src uv run --with pytest --with httpx pytest -q`
- テスト時の格納先: `INVENTORY_APP_DIR` を一時ディレクトリに設定し、ホームディレクトリを汚染しない（監査は `INVENTORY_AUDIT_DISABLED=1` で無効化）
- OpenAPIメタ: 起動時にロケールを読み込み、既定言語（ja）からタイトル/説明/タグを埋め込み
- 型/整形（インストール済みなら）:
  - `uv run ruff check src`
  - `uv run black src`

## フロントエンド（Vite + TS）
- 開発: `cd frontend && npm install && npm run dev`
- 本番ビルド: `cd frontend && npm run build`（出力先 `src/app/public`）
- 開発時は Vite の dev サーバ（http://127.0.0.1:5173）を利用（`vite.config.ts` の proxy がAPIへ転送）
 - 備考: `src/app/public` が未生成でもバックエンドは起動します（`/app` は空のため 404 のことがあります）。SPA 利用時はビルドしてください。

## 検索の実装（サマリ）
- `/stock/search` は SQL のサブクエリで在庫残高（`balance`）を集計し、SQL側でフィルタ・複合ソート・ページングを実施
- `/stock/export/csv` は検索と同条件・同ソートでSQLから直接抽出してCSV化

## 配布（PyInstaller）
- `uv run pyinstaller inventory-app.spec`
- `dist/inventory-app` を配布

## よくある課題
- SQLite ファイル: `~/.inventory-system/db.sqlite3`（初回に seed を展開）。権限に注意
- SPA ビルドが反映されない: `frontend` で `npm run build` し `src/app/public` ができているか確認
 - テンプレート/静的/ロケールを onefile に同梱する場合は `inventory-app.spec` を使うこと
 - `inventory-app.spec` は `src/app/public` が無い場合はスキップするガードを持ちますが、配布向けにはビルド済みのSPA同梱を推奨
 - CI では `backend` が `needs: frontend` で実行され、テスト時に `INVENTORY_APP_DIR` と `INVENTORY_AUDIT_DISABLED` を設定
 - 依存変更後は `uv sync` で `uv.lock` を更新して整合を取ってください。

## 簡易マイグレーション（SQLite）
- 環境変数 `INVENTORY_MIGRATE=1` で起動すると、`StockMovement.type` に CHECK 制約を付与する軽量移行を試行します。
- 既存DBの不正値は `ADJUST` に正規化してコピー後、テーブルを入れ替えます（バックアップ推奨）。
