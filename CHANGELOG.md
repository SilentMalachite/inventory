# Changelog

## v0.1.0
- 初回リリース（在庫管理API + SQLite同梱）
- i18n（日本語既定）、監査ログ
- アイテムCRUD、入出庫/調整、在庫残高/検索/推移
- Excel/CSV 入出力（Windows向けUTF-8 BOM対応）
- SPA（Vite + React + TS）: 検索（カテゴリ/範囲/低在庫/複合ソート/ページング）、選択UI、在庫推移グラフ（バー/移動平均/ツールチップ）、検索結果CSV
- PyInstaller onefile 同梱（テンプレート/静的/ロケール/SPA）

## Unreleased
- SSR トップ画面を有効化（`/`）し、SPA は `/app` に分離
- OpenAPI メタをロケール（既定: ja）から埋込
- 環境変数: `INVENTORY_APP_DIR`（DB/ログ先切替）、`INVENTORY_AUDIT_DISABLED`（監査無効化）、`INVENTORY_MIGRATE`（簡易移行）
- 検索（`/stock/search`）/CSV出力を完全SQL化（balance集計・フィルタ・複合ソート・ページング）
- `StockMovement.type` に DB CHECK 制約を追加
- CI: frontend→backend の順序実行、テスト時ENV設定
- PyInstaller spec: `public` が無い場合はスキップするガードを追加
- 依存整理（未使用の `pydantic-settings` を削除）
