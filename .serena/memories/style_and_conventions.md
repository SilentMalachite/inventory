# Style and Conventions

- Language: Default runtime language JA; maintain translations in `src/app/locales/*.json`. Use dotted keys (e.g., `errors.item_not_found`).
- API docs: Prefer Japanese `title`, `description`, and endpoint `summary`/`description`. Keep EN fallbacks in `en.json`.
- Types: Use Python type hints throughout (as in models and endpoints).
- Models: Define SQLModel models in `models.py`. Use `unique=True` for SKU, timestamps via `default_factory`.
- Database: SQLite file at `~/.inventory-system/db.sqlite3`. Copy seed on first run; always call `init_db()` on startup.
- Routers: Group domain operations (items, stock) under `src/app/routers/`. Keep business logic thin or move into `services/` if it grows.
- i18n usage: Inject translator via `Depends(get_translator)`; translate user-facing strings and exceptions.
- Imports: Absolute within package (e.g., `from .i18n import ...`).
- Formatting/linting (optional): black, ruff; typing with mypy when enabled.
