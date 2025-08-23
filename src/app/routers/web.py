from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from importlib import resources as ir
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from ..db import get_session
from ..i18n import get_translator, Translator
from ..models import Item, StockMovement
from ..services.inventory import compute_all_balances


templates = Jinja2Templates(directory=str(ir.files("app").joinpath("templates")))

router = APIRouter(include_in_schema=False)


@router.get("/")
def dashboard_redirect():
    # Full SPA requested: redirect top to /app
    return RedirectResponse(url="/app", status_code=307)


@router.get("/ui")
def spa(request: Request):
    return templates.TemplateResponse("spa.html", {"request": request})


@router.post("/web/items")
def create_item(
    request: Request,
    sku: str = Form(...),
    name: str = Form(...),
    category: Optional[str] = Form(None),
    unit: str = Form("pcs"),
    min_stock: int = Form(0),
    session: Session = Depends(get_session),
    t: Translator = Depends(get_translator),
):
    try:
        obj = Item(sku=sku.strip(), name=name.strip(), category=category or None, unit=unit.strip() or "pcs", min_stock=min_stock)
        session.add(obj)
        session.commit()
    except IntegrityError:
        session.rollback()
        return RedirectResponse(url="/?msg=" + t("errors.duplicate_sku"), status_code=303)
    return RedirectResponse(url="/?msg=商品を登録しました", status_code=303)


def _movement(session: Session, item_id: int, qty: int, ref: Optional[str], kind: str):
    m = StockMovement(item_id=item_id, qty=qty, ref=ref, type=kind)
    session.add(m)
    session.commit()


@router.post("/web/stock/in")
def stock_in(item_id: int = Form(...), qty: int = Form(...), ref: Optional[str] = Form(None), session: Session = Depends(get_session)):
    if not session.get(Item, item_id):
        raise HTTPException(404, "対象の商品が見つかりません")
    _movement(session, item_id, qty, ref, "IN")
    return RedirectResponse(url="/?msg=入庫を登録しました", status_code=303)


@router.post("/web/stock/out")
def stock_out(item_id: int = Form(...), qty: int = Form(...), ref: Optional[str] = Form(None), session: Session = Depends(get_session)):
    if not session.get(Item, item_id):
        raise HTTPException(404, "対象の商品が見つかりません")
    _movement(session, item_id, qty, ref, "OUT")
    return RedirectResponse(url="/?msg=出庫を登録しました", status_code=303)


@router.post("/web/stock/adjust")
def stock_adjust(item_id: int = Form(...), qty: int = Form(...), ref: Optional[str] = Form(None), session: Session = Depends(get_session)):
    if not session.get(Item, item_id):
        raise HTTPException(404, "対象の商品が見つかりません")
    if qty == 0:
        return RedirectResponse(url="/?msg=調整数に0は指定できません", status_code=303)
    _movement(session, item_id, qty, ref, "ADJUST")
    return RedirectResponse(url="/?msg=在庫調整を登録しました", status_code=303)
