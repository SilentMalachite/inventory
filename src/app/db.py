from pathlib import Path
import shutil
from sqlmodel import SQLModel, create_engine, Session

APP_DIR = Path.home() / ".inventory-system"
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


def get_session():
    with Session(engine) as session:
        yield session

