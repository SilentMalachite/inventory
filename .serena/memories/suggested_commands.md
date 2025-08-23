# Suggested Commands

- Dev server:
  - `uv run uvicorn app.main:app --reload`
- SPA view:
  - Open `http://127.0.0.1:8000/ui` (React UMD via CDN). For offline, vendor React to `/static/spa/vendor` and update `spa.html`.
- Build onefile (spec including templates/static/locales/assets):
  - `uv run pyinstaller inventory-app.spec`
  - Or CLI flags equivalent:
    - `uv run pyinstaller --onefile --name inventory-app --paths ./src --add-data "src/app/assets/seed.db:app/assets" --add-data "src/app/templates:app/templates" --add-data "src/app/static:app/static" --add-data "src/app/locales:app/locales" src/app/__main__.py`
- CSV/XLSX export:
  - `GET /items/export/csv` (BOM付UTF-8), `GET /items/export/xlsx`
- CSV/XLSX import (multipart):
  - `POST /items/import/csv`, `POST /items/import/xlsx`
