# 開発ガイド

## ブランチとコミット
- メイン開発は `main` を既定とし、機能ごとにブランチを切って PR
- コミットは意味のある最小単位で。推奨: Conventional Commits（例: `feat: add stock search`）

## Python 側
- 実行: `uv run uvicorn app.main:app --reload`
- テスト: `PYTHONPATH=src uv run --with pytest --with httpx pytest -q`
- 型/整形（インストール済みなら）:
  - `uv run ruff check src`
  - `uv run black src`

## フロントエンド（Vite + TS）
- 開発: `cd frontend && npm install && npm run dev`
- 本番ビルド: `cd frontend && npm run build`（出力先 `src/app/public`）
- 開発時は Vite の dev サーバ（http://127.0.0.1:5173）を利用（`vite.config.ts` の proxy がAPIへ転送）

## 配布（PyInstaller）
- `uv run pyinstaller inventory-app.spec`
- `dist/inventory-app` を配布

## よくある課題
- SQLite ファイル: `~/.inventory-system/db.sqlite3`（初回に seed を展開）。権限に注意
- SPA ビルドが反映されない: `frontend` で `npm run build` し `src/app/public` ができているか確認
- テンプレート/静的/ロケールを onefile に同梱する場合は `inventory-app.spec` を使うこと

