# Inventory System (FastAPI + SQLModel + SQLite + SPA)

在庫管理APIとダッシュボード（SPA）を備えたサンプル実装です。uv でPython環境を管理し、Vite + TypeScript + React でフロントエンドを構築、PyInstaller `onefile` で単一実行ファイルに同梱できます。

## 特長
- FastAPI + SQLModel + SQLite（初回起動時にユーザ領域へ展開）
- i18n（日本語既定、`Accept-Language`/`?lang=` 切替）
- API: 商品CRUD, 入出庫/調整, 在庫残高, 在庫検索（カテゴリ/範囲/低在庫/ページング/複合ソート）, 在庫推移
- 監査ログ（JSON Lines, `~/.inventory-system/app.log`）
- Excel/CSV 入出力（Windows Excel向け `utf-8-sig` 対応）
- WebUI: SPA（/app）。選択UI・在庫検索・推移グラフを実装
- PyInstaller onefile 同梱（テンプレート/静的/ロケール/SPAビルドを含む）

## 必要要件
- Python 3.10+
- uv（https://docs.astral.sh/uv/）
- Node.js 18+（SPAのビルドに必要）

## セットアップと起動
1) 依存の解決（バックエンド）
- 開発起動: `uv run uvicorn app.main:app --reload`

2) フロントエンド（開発）
- `cd frontend`
- `npm install`
- `npm run dev`（http://127.0.0.1:5173, プロキシでAPIへ）

3) フロントエンド（本番ビルド）
- `cd frontend && npm run build`
- ビルド成果物は `src/app/public` へ出力され、FastAPI が `/app` で配信

4) 画面
- SPA: `http://127.0.0.1:8000/`（ルートは `/app` にリダイレクト）

## 主なエンドポイント
- ヘルス: `GET /health`
- 商品: `POST/GET/PUT/DELETE /items`, `GET /items/{id}`, `GET /items/categories`, `POST /items/categories/rename`, `POST /items/categories/delete`
- 入出庫: `POST /stock/in|out|adjust`
- 在庫: `GET /stock/balance/{id}`, `GET /stock/balances`
- 検索: `GET /stock/search`（q, category, low_only, min/max_balance, sort_by, sort_dir, page, size）
- 推移: `GET /stock/trend/{id}?days=N`
- 出力: `GET /items/export/csv|xlsx`（全件） / `GET /stock/export/csv`（検索結果のみ）
- WebUI: `/app`（SPA）

## i18n
- 既定: 日本語（`ja`）
- 切替: `Accept-Language: en` や `?lang=en`
- 定義: `src/app/locales/ja.json`, `en.json`

## 監査ログ
- 場所: `~/.inventory-system/app.log`（JSON Lines）
- 記録: アプリ起動、HTTPアクセス、商品CRUD、入出庫/調整、インポート等

## PyInstaller（配布）
- ビルド: `uv run pyinstaller inventory-app.spec`
- 生成物: `dist/inventory-app`
- 備考: 各OSはそのOS上でビルド（クロスビルド不可）

## テスト
- 最低限のAPIテスト例: `tests/test_api.py`
- 実行:
  - `PYTHONPATH=src uv run --with pytest --with httpx pytest -q`

## 開発メモ
- バックエンド: `src/app/`（`main.py`, `routers/`, `services/`, `models.py`, `schemas.py`）
- フロントエンド: `frontend/`（Vite -> `src/app/public` 出力）
- 生成物: `.gitignore` で `src/app/public` は除外（配布時はビルド→PyInstaller 同梱）

## ライセンス
- プロジェクトに適切なライセンスを追加してください（未設定）。

## CI（GitHub Actions）
- Push/PR でバックエンドのテストとフロントのビルドを実行（.github/workflows/ci.yml）
- タグで各OS向けに onefile をビルドしアーティファクト化（.github/workflows/release.yml）
