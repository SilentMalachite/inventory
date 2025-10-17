from __future__ import annotations

from importlib import resources as ir

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from ..db import get_session
from ..i18n import Translator, get_translator
from ..models import Item, StockMovement
from ..security import get_csrf_token, require_basic_auth, validate_csrf_or_400
from ..services.inventory import compute_all_balances

templates = Jinja2Templates(directory=str(ir.files("app").joinpath("templates")))

router = APIRouter(include_in_schema=False)


@router.get("/")
def index(request: Request, session: Session = Depends(get_session)):
    # Render SSR dashboard
    items = session.exec(select(Item)).all()
    balances = compute_all_balances(session)
    rows = []
    for it in items:
        bal = balances.get(it.id or 0, 0)
        rows.append(
            {
                "id": it.id,
                "sku": it.sku,
                "name": it.name,
                "category": it.category,
                "unit": it.unit,
                "min_stock": it.min_stock,
                "balance": bal,
                "low": bal < (it.min_stock or 0),
            }
        )
    return templates.TemplateResponse(
        "index.html",
        {"request": request, "items": rows, "csrf_token": get_csrf_token(request)},
    )


@router.get("/ui")
def spa(request: Request):
    return templates.TemplateResponse("spa.html", {"request": request})


@router.post("/web/items")
def create_item(
    request: Request,
    sku: str = Form(...),
    name: str = Form(...),
    category: str | None = Form(None),
    unit: str = Form("pcs"),
    min_stock: int = Form(0),
    csrf_token: str = Form(...),
    session: Session = Depends(get_session),
    t: Translator = Depends(get_translator),
    _: None = Depends(require_basic_auth),
):
    validate_csrf_or_400(request, csrf_token)
    try:
        obj = Item(
            sku=sku.strip(),
            name=name.strip(),
            category=category or None,
            unit=unit.strip() or "pcs",
            min_stock=min_stock,
        )
        session.add(obj)
        session.commit()
    except IntegrityError:
        session.rollback()
        return RedirectResponse(
            url="/?msg=" + t("errors.duplicate_sku"), status_code=303
        )
    return RedirectResponse(url="/?msg=商品を登録しました", status_code=303)


def _movement(session: Session, item_id: int, qty: int, ref: str | None, kind: str):
    m = StockMovement(item_id=item_id, qty=qty, ref=ref, type=kind)
    session.add(m)
    session.commit()


@router.post("/web/stock/in")
def stock_in(
    request: Request,
    item_id: int = Form(...),
    qty: int = Form(...),
    ref: str | None = Form(None),
    csrf_token: str = Form(...),
    session: Session = Depends(get_session),
    _: None = Depends(require_basic_auth),
):
    validate_csrf_or_400(request, csrf_token)
    if not session.get(Item, item_id):
        raise HTTPException(404, "対象の商品が見つかりません")
    _movement(session, item_id, qty, ref, "IN")
    return RedirectResponse(url="/?msg=入庫を登録しました", status_code=303)


@router.post("/web/stock/out")
def stock_out(
    request: Request,
    item_id: int = Form(...),
    qty: int = Form(...),
    ref: str | None = Form(None),
    csrf_token: str = Form(...),
    session: Session = Depends(get_session),
    _: None = Depends(require_basic_auth),
):
    validate_csrf_or_400(request, csrf_token)
    if not session.get(Item, item_id):
        raise HTTPException(404, "対象の商品が見つかりません")
    _movement(session, item_id, qty, ref, "OUT")
    return RedirectResponse(url="/?msg=出庫を登録しました", status_code=303)


@router.post("/web/stock/adjust")
def stock_adjust(
    request: Request,
    item_id: int = Form(...),
    qty: int = Form(...),
    ref: str | None = Form(None),
    csrf_token: str = Form(...),
    session: Session = Depends(get_session),
    _: None = Depends(require_basic_auth),
):
    validate_csrf_or_400(request, csrf_token)
    if not session.get(Item, item_id):
        raise HTTPException(404, "対象の商品が見つかりません")
    if qty == 0:
        return RedirectResponse(url="/?msg=調整数に0は指定できません", status_code=303)
    _movement(session, item_id, qty, ref, "ADJUST")
    return RedirectResponse(url="/?msg=在庫調整を登録しました", status_code=303)
