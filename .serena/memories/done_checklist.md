# Done Checklist (DoD)

- GET `/health` returns 200 and JA status by default ("正常").
- `/items` supports create with unique SKU and list; duplicate SKU returns 409 with JA message.
- `/stock/in` persists a stock movement; non-existent item returns 404 with JA message.
- `uv run` can launch the dev server.
- PyInstaller onefile can be built including `seed.db` and runs using `~/.inventory-system/db.sqlite3` for persistence.
- i18n: Accept-Language header or `?lang=` switches language; `Content-Language` header is present.
