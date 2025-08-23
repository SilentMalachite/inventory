# リリース手順

1. バージョン更新（必要に応じて `src/app/__init__.py` の `__version__` を更新）
2. フロントエンドをビルド
   - `cd frontend && npm install && npm run build`
3. onefile を生成
   - `uv run pyinstaller inventory-app.spec`
4. 動作確認
   - `./dist/inventory-app` を起動
   - ブラウザで `/app` と主要APIを確認
5. 署名/ノータライズ（配布ポリシーに準拠）
6. リリースノート作成（CHANGELOG）

> 各OSはそのOS上でビルドしてください（クロスビルド不可）。

