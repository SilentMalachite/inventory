from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.staticfiles import StaticFiles
from importlib import resources as ir
from starlette.middleware.sessions import SessionMiddleware
import os

from .db import init_db, migrate_if_requested
from .routers import items, stock, web
from .i18n import LocaleMiddleware, get_translator, load_translations, Translator, translate, DEFAULT_LANG
from .audit import audit
from .security import require_api_key

# OpenAPI は起動時に固定値が必要なため、既定言語(ja)のロケールから埋め込む
load_translations()
app = FastAPI(
    title=translate(DEFAULT_LANG, "docs.title"),
    description=translate(DEFAULT_LANG, "docs.description"),
    openapi_tags=[
        {"name": "items", "description": translate(DEFAULT_LANG, "docs.tags.items")},
        {"name": "stock", "description": translate(DEFAULT_LANG, "docs.tags.stock")},
    ],
)
app.add_middleware(LocaleMiddleware)
app.add_middleware(
    SessionMiddleware,
    secret_key=os.environ.get("INVENTORY_SECRET_KEY", "dev-secret-key"),
    same_site="lax",
)

# Static files for Web UI
app.mount("/static", StaticFiles(directory=str(ir.files("app").joinpath("static"))), name="static")
# Serve SPA build (Vite outDir -> app/public)
# public は開発・CI では未生成のことがあるため、check_dir=False でマウントして起動時エラーを回避
app.mount(
    "/app",
    StaticFiles(directory=str(ir.files("app").joinpath("public")), html=True, check_dir=False),
    name="spa",
)


@app.on_event("startup")
def on_startup():
    init_db()
    migrate_if_requested()
    load_translations()
    audit("app.start")


@app.get("/health")
def health(t: Translator = Depends(get_translator)):
    return {"status": t("status.ok")}


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    # Simple JA-friendly message with field-level messages mapped when possible
    lang = getattr(request.state, "lang", "ja")

    def ja_msg(msg: str) -> str:
        m = msg.lower()
        if "field required" in m:
            return "必須項目です"
        if "value is not a valid integer" in m:
            return "整数として不正です"
        if "ensure this value is greater than 0" in m:
            return "0より大きい値を指定してください"
        if "ensure this value is greater than or equal to 0" in m:
            return "0以上の値を指定してください"
        if "value is not a valid" in m:
            return "値が不正です"
        return msg

    errors = []
    for e in exc.errors():
        loc = ".".join(str(p) for p in e.get("loc", []) if p != "body")
        errors.append({
            "field": loc,
            "message": ja_msg(e.get("msg", "")) if lang == "ja" else e.get("msg", ""),
        })
    detail = translate(lang, "errors.validation_failed")
    if detail == "errors.validation_failed":
        detail = "入力値が不正です" if lang == "ja" else "Invalid input"
    return JSONResponse(status_code=422, content={"detail": detail, "errors": errors})


# 簡易アクセスログ（監査用）
@app.middleware("http")
async def access_log(request: Request, call_next):
    response = await call_next(request)
    try:
        audit(
            "http.access",
            method=request.method,
            path=str(request.url.path),
            status=response.status_code,
            lang=getattr(request.state, "lang", "ja"),
        )
    except Exception:
        pass
    return response


app.include_router(items.router, prefix="/items", tags=["items"], dependencies=[Depends(require_api_key)])
app.include_router(stock.router, prefix="/stock", tags=["stock"], dependencies=[Depends(require_api_key)])
app.include_router(web.router)
