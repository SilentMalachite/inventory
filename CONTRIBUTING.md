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
- エラーハンドリング: `@handle_api_errors` デコレータを使用して一貫したエラー処理

## スタイル
- コード品質チェック: `python quality.py` で全てのチェックを実行
- 個別チェック:
  - フォーマット: `python quality.py format`
  - リント: `python quality.py lint`
  - 型チェック: `python quality.py type`
  - テスト: `python quality.py test`
  - セキュリティスキャン: `python quality.py security`
- Pre-commitフック: `python quality.py setup-pre-commit` でインストール

## コミット・PR
- Conventional Commits を推奨
- タイトルは 50 文字以内、説明は必要に応じて詳細化
- スクリーンショット/ログ/再現方法を添付するとレビューが円滑です

## リリース
- `docs/RELEASE.md` を参照（フロントをビルド→PyInstaller onefile 生成）

