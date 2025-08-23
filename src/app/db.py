from pathlib import Path
import os
import shutil
from sqlmodel import SQLModel, create_engine, Session

APP_DIR = Path(os.environ.get("INVENTORY_APP_DIR", Path.home() / ".inventory-system"))
APP_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = APP_DIR / "db.sqlite3"

# Bundle seed at src/app/assets/seed.db and copy on first run
SEED = Path(__file__).parent / "assets" / "seed.db"
if not DB_PATH.exists() and SEED.exists():
    try:
        shutil.copy(SEED, DB_PATH)
    except Exception:
        # Fallback: ensure file exists even if copy fails
        DB_PATH.touch(exist_ok=True)

engine = create_engine(f"sqlite:///{DB_PATH}", connect_args={"check_same_thread": False})


def init_db() -> None:
    SQLModel.metadata.create_all(engine)


def migrate_if_requested() -> None:
    """Optional, SQLite-only lightweight migration for adding CHECK constraint on stockmovement.type.
    Enabled when INVENTORY_MIGRATE=1.
    """
    import os
    if os.environ.get("INVENTORY_MIGRATE", "") not in ("1", "true", "TRUE", "True"):
        return
    from sqlalchemy import text
    with engine.begin() as conn:
        # Only for SQLite
        dialect = conn.dialect.name
        if dialect != "sqlite":
            return
        # Inspect current table DDL
        row = conn.execute(text("SELECT sql FROM sqlite_master WHERE type='table' AND name='stockmovement'")) .fetchone()
        ddl = row[0] if row and row[0] else ""
        if "ck_stockmovement_type" in ddl:
            return  # already migrated
        # Create new table with constraint, copy data, swap
        conn.execute(text(
            """
            PRAGMA foreign_keys=off;
            CREATE TABLE stockmovement_new (
              id INTEGER PRIMARY KEY,
              item_id INTEGER NOT NULL,
              type TEXT NOT NULL CHECK(type IN ('IN','OUT','ADJUST')),
              qty INTEGER NOT NULL,
              ref TEXT,
              moved_at DATETIME NOT NULL,
              FOREIGN KEY(item_id) REFERENCES item(id)
            );
            INSERT INTO stockmovement_new (id,item_id,type,qty,ref,moved_at)
            SELECT id, item_id,
                   CASE WHEN type IN ('IN','OUT','ADJUST') THEN type ELSE 'ADJUST' END,
                   qty, ref, moved_at
            FROM stockmovement;
            ALTER TABLE stockmovement RENAME TO stockmovement_old;
            ALTER TABLE stockmovement_new RENAME TO stockmovement;
            DROP TABLE stockmovement_old;
            CREATE INDEX IF NOT EXISTS ix_stockmovement_item_id ON stockmovement(item_id);
            PRAGMA foreign_keys=on;
            """
        ))


def get_session():
    with Session(engine) as session:
        yield session
