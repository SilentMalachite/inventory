# Contributing

ありがとうございます。以下のガイドにしたがってコントリビュートをお願いします。

## 開発フロー
- Issue を立て、仕様・受入条件を簡潔に整理
- `feat/...` や `fix/...` のブランチを作成
- 小さな PR に分け、レビューを通してから `main` にマージ

## コーディング
- Python: 型ヒントを付け、関数は短く保つ
- i18n: ユーザ向け文言は `src/app/locales/*.json` にキー追加し、`get_translator` で注入した翻訳関数を使用
- 監査: 重要操作は `src/app/audit.py` の `audit()` を呼び出し記録
- テスト: ユニットテストを `tests/` に追加（FastAPI TestClient を利用）

## スタイル
- 整形/静的解析（インストール済みの場合）:
  - `uv run black src`
  - `uv run ruff check src`

## コミット・PR
- Conventional Commits を推奨
- タイトルは 50 文字以内、説明は必要に応じて詳細化
- スクリーンショット/ログ/再現方法を添付するとレビューが円滑です

## リリース
- `docs/RELEASE.md` を参照（フロントをビルド→PyInstaller onefile 生成）

