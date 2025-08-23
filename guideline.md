# INVENTORY-SYSTEM-SQLITE.md（AIエージェント向け指示・単一ファイル）

最終更新: 2025-08-23 06:52:11

本書は **uv** を使って環境・依存を一元管理し、**FastAPI** + **SQLModel** + **SQLite（同梱）** で在庫管理APIを実装、**PyInstaller** の `--onefile` で **Python本体同梱の単一実行ファイル** を生成するための指示書です。  
対象OS: Windows / macOS / Linux（各OSは**そのOS上で**ビルドすること）

---

## 0. 根拠・公式ドキュメント
- uv 公式ドキュメント（高速なPythonパッケージ＆プロジェクトマネージャ）  
  → docs: https://docs.astral.sh/uv/  
- uv の背景（pip代替・高速解決）  
  → blog: https://astral.sh/blog/uv  
- FastAPI 公式（ASGI・自動ドキュメント）  
  → https://fastapi.tiangolo.com/  
- Uvicorn 公式（ASGIサーバ）  
  → https://www.uvicorn.org/  
- SQLModel 公式（Pydantic + SQLAlchemy ベース）  
  → https://sqlmodel.tiangolo.com/  
- PyInstaller マニュアル（Python本体も収集し単一exe/onefile可能）  
  → https://www.pyinstaller.org/ / https://pyinstaller.org/en/stable/operating-mode.html / https://pyinstaller.org/en/stable/usage.html / https://pyinstaller.org/en/stable/spec-files.html

---

## 1. 要件と方針

- **Python**: 3.10+（推奨 3.11）
- **パッケージ/環境管理**: `uv`（Python本体のインストール、仮想環境、依存解決、実行を一元化）
- **Webフレームワーク**: FastAPI（Pydantic v2）
- **ASGIサーバ**: Uvicorn（開発時は `--reload`）
- **ORM/モデル**: SQLModel（SQLite→将来PostgreSQLに拡張可能）
- **DB**: SQLite **同梱**（空のテンプレートDBをパッケージに含め、初回起動時にユーザ領域へ展開）
- **配布**: PyInstaller `--onefile`（**Python不要で実行**）

> 注: `--onefile` は実行時に一時展開を行います。企業配布では署名/ノータリゼーション等も検討。

---

## 2. プロジェクト初期化（uv）

```bash
# 初期化
uv init inventory-system
cd inventory-system

# Pythonインストール（例: 3.11）
uv python install 3.11

# 実装依存
uv add fastapi "uvicorn[standard]" sqlmodel pydantic-settings

# 開発補助
uv add -d ruff black mypy pytest httpx pyinstaller
```

**開発起動**：
```bash
uv run uvicorn app.main:app --reload
```

---

## 3. ディレクトリ構成（推奨）

```
inventory-system/
  pyproject.toml
  uv.lock
  src/
    app/
      __init__.py
      main.py
      db.py
      models.py
      schemas.py
      deps.py
      routers/
        items.py
        stock.py
      services/
        inventory.py
      assets/
        seed.db        # ★ SQLiteの空テンプレートDB（同梱）
  tests/
```

- **SQLite同梱方針**: `src/app/assets/seed.db` を `--add-data` でバンドル。初回起動時にユーザ領域（例: `~/.inventory-system/db.sqlite3`）へコピーし、以降はそちらを使用。
- Pythonの `sqlite3` モジュールは同梱Pythonにより動作。OS固有のsqliteライブラリはPyInstallerが依存解析の上で収集するため、通常は追加設定不要。必要に応じてspecファイルで明示。

---

## 4. 最小実装

### 4.1 `src/app/db.py`
```python
from sqlmodel import SQLModel, create_engine, Session
from pathlib import Path
import shutil, os

APP_DIR = Path.home() / ".inventory-system"
APP_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = APP_DIR / "db.sqlite3"

# 初回展開: assets/seed.db -> ~/.inventory-system/db.sqlite3
SEED = Path(__file__).parent / "assets" / "seed.db"
if not DB_PATH.exists() and SEED.exists():
    shutil.copy(SEED, DB_PATH)

engine = create_engine(f"sqlite:///{DB_PATH}", connect_args={"check_same_thread": False})

def init_db():
    SQLModel.metadata.create_all(engine)

def get_session():
    with Session(engine) as session:
        yield session
```

### 4.2 `src/app/models.py`
```python
from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, List
from datetime import datetime

class Item(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    sku: str = Field(index=True, unique=True)
    name: str
    category: Optional[str] = None
    unit: str = "pcs"
    min_stock: int = 0
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    movements: List["StockMovement"] = Relationship(back_populates="item")

class StockMovement(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    item_id: int = Field(foreign_key="item.id", index=True)
    type: str  # "IN" | "OUT" | "ADJUST"
    qty: int
    ref: Optional[str] = None
    moved_at: datetime = Field(default_factory=datetime.utcnow)
    item: Item = Relationship(back_populates="movements")
```

### 4.3 `src/app/routers/items.py`
```python
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import select
from ..db import get_session
from ..models import Item
from sqlmodel import Session

router = APIRouter()

@router.post("/", response_model=Item, status_code=201)
def create_item(item: Item, session: Session = Depends(get_session)):
    session.add(item)
    session.commit()
    session.refresh(item)
    return item

@router.get("/", response_model=list[Item])
def list_items(session: Session = Depends(get_session)):
    return session.exec(select(Item)).all()
```

### 4.4 `src/app/routers/stock.py`
```python
from fastapi import APIRouter, Depends, HTTPException
from ..db import get_session
from ..models import StockMovement, Item
from sqlmodel import Session, select

router = APIRouter()

@router.post("/in", response_model=StockMovement, status_code=201)
def stock_in(m: StockMovement, session: Session = Depends(get_session)):
    item = session.get(Item, m.item_id)
    if not item:
        raise HTTPException(404, "item not found")
    session.add(m)
    session.commit()
    session.refresh(m)
    return m
```

### 4.5 `src/app/main.py`
```python
from fastapi import FastAPI
from .db import init_db
from .routers import items, stock

app = FastAPI(title="Inventory System (SQLite bundled)")

@app.on_event("startup")
def on_startup():
    init_db()

@app.get("/health")
def health():
    return {"status": "ok"}

app.include_router(items.router, prefix="/items", tags=["items"])
app.include_router(stock.router, prefix="/stock", tags=["stock"])
```

---

## 5. 起動・テスト

```bash
# 開発サーバ（ホットリロード）
uv run uvicorn app.main:app --reload

# API テスト（例）
uv add -d pytest httpx
uv run pytest -q
```

---

## 6. 配布（Python同梱・単一ファイル）

### 6.1 エントリポイント
`src/app/__main__.py` を用意して `python -m app` で起動可能に：
```python
from .main import app
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
```

### 6.2 PyInstaller onefile
```bash
uv run pyinstaller --onefile --name inventory-app   --paths ./src   --add-data "src/app/assets/seed.db:app/assets"   src/app/__main__.py
```
- 出力: `dist/inventory-app`（OSごとに拡張子）
- `--add-data` で **seed.db** を同梱（onefileでも実行時解凍される）
- 生成された `inventory-app.spec` を編集すれば、同梱ファイル・隠しimport等を詳細制御可能

**注意**：各OSは**そのOS上でビルド**（クロスビルド不可）。コード署名/ノータライズは配布要件に従う。

---

## 7. 設定・運用指針

- **DBの永続場所**: `~/.inventory-system/db.sqlite3`（アプリ更新で消えない場所）
- **設定管理**: `pydantic-settings` + `.env`（例: `DATABASE_URL` の差替えで PostgreSQL へ移行）
- **ログ**: APIアクセス/在庫操作を構造化ログ化（監査対応）
- **パフォーマンス**: Uvicornワーカー数・リバプロ（nginx）検討
- **拡張**: 認証(JWT/OAuth2)、低在庫通知、棚卸、CSV/Excel I/O、バーコード、複数倉庫

---

## 8. 受け入れ基準（DoD）
- `GET /health` が 200 を返す
- `/items` CRUD と入出庫APIがSQLiteに永続化
- `uv run` で開発起動可能
- 各OS向け onefile 実行ファイルが **Python未インストール環境でも起動** し、APIが利用できる

---

## 9. トラブルシュート（SQLite同梱）
- **seed.dbが見つからない**: `--add-data` のパスと展開先を再確認（OSごとに区切り記号 `;`/`:` が異なるため、上記例の形式を踏襲）
- **sqlite3動かない**: PyInstallerの自動収集に失敗した場合は spec に `binaries` を追加。Python配布に含まれる `sqlite3` DLL/so を明示収集
- **権限/AV遅延**: onefileは実行時展開を行うため、ウイルス対策による遅延・誤検知に留意

---

## 10. 参考（公式）
- uv: docs / blog  
- FastAPI: チュートリアル/デプロイ/ASGIサーバ（Uvicorn）
- Uvicorn: 公式  
- SQLModel: 公式  
- PyInstaller: Manual / Operating-mode（Python本体を含める説明） / Usage / Spec files
