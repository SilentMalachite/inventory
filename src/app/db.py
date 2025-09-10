from pathlib import Path
import os
import shutil
from contextlib import contextmanager
from typing import Generator
from sqlmodel import SQLModel, create_engine, Session, or_
from sqlalchemy import event
from sqlalchemy.exc import SQLAlchemyError, IntegrityError

def _resolve_app_dir() -> Path:
    """アプリ用ディレクトリの決定（権限制約に強い実装）。
    優先順位: ENV(`INVENTORY_APP_DIR`) -> `~/.inventory-system` -> `CWD/.inventory-system`
    """
    # 1) 環境変数優先
    def _writable(d: Path) -> bool:
        try:
            d.mkdir(parents=True, exist_ok=True)
            test = d / ".write_test"
            test.write_text("ok", encoding="utf-8")
            test.unlink(missing_ok=True)
            return True
        except Exception:
            return False

    env_dir = os.environ.get("INVENTORY_APP_DIR")
    if env_dir:
        p = Path(env_dir).expanduser()
        if _writable(p):
            return p
    # 2) ホーム配下
    p = Path.home() / ".inventory-system"
    if _writable(p):
        return p
    # 3) 作業ディレクトリ配下
    p = Path.cwd() / ".inventory-system"
    p.mkdir(parents=True, exist_ok=True)
    return p


APP_DIR = _resolve_app_dir()
DB_PATH = APP_DIR / "db.sqlite3"

# Bundle seed at src/app/assets/seed.db and copy on first run
SEED = Path(__file__).parent / "assets" / "seed.db"
if not DB_PATH.exists():
    try:
        if SEED.exists():
            shutil.copy(SEED, DB_PATH)
        else:
            DB_PATH.touch(exist_ok=True)
    except Exception:
        # 最終フォールバック: CWD 配下に作成
        fallback = Path.cwd() / ".inventory-system"
        fallback.mkdir(parents=True, exist_ok=True)
        DB_PATH = fallback / "db.sqlite3"
        DB_PATH.touch(exist_ok=True)

engine = create_engine(
    f"sqlite:///{DB_PATH}",
    connect_args={"check_same_thread": False, "timeout": 30},
)


@event.listens_for(engine, "connect")
def _set_sqlite_pragma(dbapi_connection, connection_record):
    try:
        cursor = dbapi_connection.cursor()
        try:
            cursor.execute("PRAGMA journal_mode=WAL;")
            cursor.execute("PRAGMA synchronous=NORMAL;")
            cursor.execute("PRAGMA busy_timeout=5000;")
        finally:
            cursor.close()
    except Exception:
        # Best effort; ignore if not sqlite or fails
        pass


def init_db() -> None:
    SQLModel.metadata.create_all(engine)


def migrate_if_requested() -> None:
    """SQLite向け軽量マイグレーション。
    実行条件: 環境変数 `INVENTORY_MIGRATE` が 1/true/yes の場合のみ。

    保証事項:
      - stockmovement.type の CHECK 制約
      - item.version 列（INT NOT NULL DEFAULT 0）
      - stockmovement.version / stockmovement.meta 列
    """
    if os.environ.get("INVENTORY_MIGRATE", "").lower() not in ("1", "true", "yes"):
        return
    from sqlalchemy import text
    with engine.connect() as conn:
        if conn.dialect.name != "sqlite":
            return
        # 1) Ensure stockmovement.type CHECK constraint
        row = conn.execute(text("SELECT sql FROM sqlite_master WHERE type='table' AND name='stockmovement'")) .fetchone()
        ddl = row[0] if row and row[0] else ""
        if "ck_stockmovement_type" not in ddl:
            sql_script = """
            PRAGMA foreign_keys=off;
            CREATE TABLE stockmovement_new (
              id INTEGER PRIMARY KEY,
              item_id INTEGER NOT NULL,
              type TEXT NOT NULL CHECK(type IN ('IN','OUT','ADJUST')),
              qty INTEGER NOT NULL,
              ref TEXT,
              moved_at DATETIME NOT NULL,
              version INTEGER NOT NULL DEFAULT 0,
              meta TEXT NOT NULL DEFAULT '{}',
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
            raw = conn.connection
            raw.executescript(sql_script)
        # 2) Ensure item.version exists
        cols = [r[1] for r in conn.execute(text("PRAGMA table_info('item')")).fetchall()]
        if "version" not in cols:
            conn.execute(text("ALTER TABLE item ADD COLUMN version INTEGER NOT NULL DEFAULT 0"))
        # 3) Ensure stockmovement.version and stockmovement.meta exist
        sm_cols = [r[1] for r in conn.execute(text("PRAGMA table_info('stockmovement')")).fetchall()]
        if "version" not in sm_cols:
            conn.execute(text("ALTER TABLE stockmovement ADD COLUMN version INTEGER NOT NULL DEFAULT 0"))
        if "meta" not in sm_cols:
            conn.execute(text("ALTER TABLE stockmovement ADD COLUMN meta TEXT NOT NULL DEFAULT '{}'"))


def get_session() -> Generator[Session, None, None]:
    """セッションを取得するコンテキストマネージャー
    
    Example:
        with get_session() as session:
            # トランザクション内の処理
            item = session.get(Item, item_id)
            item.name = "New Name"
    """
    session = Session(engine)
    try:
        yield session
        session.commit()
    except Exception as e:
        session.rollback()
        raise e
    finally:
        session.close()


def with_transaction(session: Session):
    """トランザクションを明示的に開始するデコレータ
    
    Example:
        @with_transaction(session)
        def update_item(session, item_id, new_name):
            item = session.get(Item, item_id)
            item.name = new_name
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            try:
                result = func(session, *args, **kwargs)
                session.commit()
                return result
            except Exception as e:
                session.rollback()
                raise e
        return wrapper
    return decorator
