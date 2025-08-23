from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from datetime import datetime
import io
from sqlmodel import Session

from ..db import get_session
from ..models import Item, StockMovement
from ..i18n import get_translator, Translator
from ..schemas import StockIn, StockOut, StockAdjust
from ..services.inventory import compute_item_balance, compute_all_balances, compute_balances_for_items
from ..audit import audit
from sqlmodel import select

router = APIRouter()


@router.post(
    "/in",
    response_model=StockMovement,
    status_code=201,
    summary="入庫を登録",
    description="指定した商品に対する入庫を記録します。",
)
def stock_in(
    payload: StockIn,
    session: Session = Depends(get_session),
    t: Translator = Depends(get_translator),
):
    item = session.get(Item, payload.item_id)
    if not item:
        raise HTTPException(404, t("errors.item_not_found"))
    m = StockMovement(item_id=payload.item_id, type="IN", qty=payload.qty, ref=payload.ref)
    session.add(m)
    session.commit()
    session.refresh(m)
    audit("stock.in", item_id=payload.item_id, qty=payload.qty, ref=payload.ref)
    return m


@router.post(
    "/out",
    response_model=StockMovement,
    status_code=201,
    summary="出庫を登録",
    description="指定した商品に対する出庫を記録します。",
)
def stock_out(
    payload: StockOut,
    session: Session = Depends(get_session),
    t: Translator = Depends(get_translator),
):
    item = session.get(Item, payload.item_id)
    if not item:
        raise HTTPException(404, t("errors.item_not_found"))
    m = StockMovement(item_id=payload.item_id, type="OUT", qty=payload.qty, ref=payload.ref)
    session.add(m)
    session.commit()
    session.refresh(m)
    audit("stock.out", item_id=payload.item_id, qty=payload.qty, ref=payload.ref)
    return m


@router.post(
    "/adjust",
    response_model=StockMovement,
    status_code=201,
    summary="在庫調整を登録",
    description="実在庫との差異を調整として記録します（正負可、0不可）。",
)
def stock_adjust(
    payload: StockAdjust,
    session: Session = Depends(get_session),
    t: Translator = Depends(get_translator),
):
    item = session.get(Item, payload.item_id)
    if not item:
        raise HTTPException(404, t("errors.item_not_found"))
    m = StockMovement(item_id=payload.item_id, type="ADJUST", qty=payload.qty, ref=payload.ref)
    session.add(m)
    session.commit()
    session.refresh(m)
    audit("stock.adjust", item_id=payload.item_id, qty=payload.qty, ref=payload.ref)
    return m


@router.get(
    "/balance/{item_id}",
    summary="在庫残高を取得",
    description="指定した商品の現在の在庫数（入庫-出庫±調整の合計）を返します。",
)
def get_balance(item_id: int, session: Session = Depends(get_session), t: Translator = Depends(get_translator)):
    item = session.get(Item, item_id)
    if not item:
        raise HTTPException(404, t("errors.item_not_found"))
    return {"item_id": item_id, "balance": compute_item_balance(session, item_id)}


@router.get(
    "/balances",
    summary="全商品の在庫残高を取得",
    description="全商品の現在在庫数を item_id をキーに返します。",
)
def get_all_balances(session: Session = Depends(get_session)):
    return compute_all_balances(session)


@router.get(
    "/search",
    summary="在庫検索",
    description="キーワード/カテゴリ/在庫範囲/低在庫のみ で検索し、在庫残高付きで返します。",
)
def search_inventory(
    q: str | None = Query(None, description="SKU/商品名/カテゴリの部分一致"),
    category: str | None = Query(None, description="カテゴリ完全一致（省略可）"),
    low_only: bool = Query(False, description="最低在庫を下回る商品のみ"),
    min_balance: int | None = Query(None, description="在庫数の最小値"),
    max_balance: int | None = Query(None, description="在庫数の最大値"),
    sort_by: str = Query("id", description="カンマ区切り可: id,sku,name,category,balance,min_stock"),
    sort_dir: str = Query("asc", description="カンマ区切り可: asc または desc"),
    page: int = Query(1, ge=1, description="ページ番号(1開始)"),
    size: int = Query(20, ge=1, le=200, description="1ページ件数"),
    session: Session = Depends(get_session),
):
    from sqlalchemy import func, case
    from sqlmodel import select

    bal_expr = func.sum(case((StockMovement.type == "IN", StockMovement.qty), (StockMovement.type == "OUT", -StockMovement.qty), else_=StockMovement.qty))
    bq = select(StockMovement.item_id, bal_expr.label("balance")).group_by(StockMovement.item_id).subquery("b")

    bal_col = func.coalesce(bq.c.balance, 0)
    base = select(Item, bal_col.label("balance")).select_from(Item).join(bq, bq.c.item_id == Item.id, isouter=True)

    # filters
    if q:
        like = f"%{q}%"
        base = base.where((Item.sku.ilike(like)) | (Item.name.ilike(like)) | (Item.category.ilike(like)))
    if category:
        base = base.where(Item.category == category)
    if min_balance is not None:
        base = base.where(bal_col >= min_balance)
    if max_balance is not None:
        base = base.where(bal_col <= max_balance)
    if low_only:
        base = base.where(bal_col < func.coalesce(Item.min_stock, 0))

    # total count
    count_stmt = select(func.count()).select_from(Item).join(bq, bq.c.item_id == Item.id, isouter=True)
    if q:
        like = f"%{q}%"
        count_stmt = count_stmt.where((Item.sku.ilike(like)) | (Item.name.ilike(like)) | (Item.category.ilike(like)))
    if category:
        count_stmt = count_stmt.where(Item.category == category)
    if min_balance is not None:
        count_stmt = count_stmt.where(bal_col >= min_balance)
    if max_balance is not None:
        count_stmt = count_stmt.where(bal_col <= max_balance)
    if low_only:
        count_stmt = count_stmt.where(bal_col < func.coalesce(Item.min_stock, 0))
    total = session.exec(count_stmt).scalar_one()

    # ordering
    keys = [k.strip() for k in sort_by.split(',') if k.strip()]
    dirs = [d.strip().lower() for d in sort_dir.split(',') if d.strip()]
    order_terms = []
    for idx, k in enumerate(keys or ["id"]):
        direction = dirs[idx] if idx < len(dirs) else "asc"
        if k == "id":
            col = Item.id
        elif k == "sku":
            col = Item.sku
        elif k == "name":
            col = Item.name
        elif k == "category":
            col = Item.category
        elif k == "min_stock":
            col = Item.min_stock
        elif k == "balance":
            col = bal_col
        else:
            col = Item.id
        order_terms.append(col.desc() if direction == "desc" else col.asc())
    base = base.order_by(*order_terms)

    # pagination
    base = base.offset((page - 1) * size).limit(size)

    rows = session.exec(base).all()
    items_page = []
    for it, bal in rows:
        bal = bal or 0
        items_page.append({
            "id": it.id,
            "sku": it.sku,
            "name": it.name,
            "category": it.category,
            "unit": it.unit,
            "min_stock": it.min_stock,
            "balance": bal,
            "low": bal < (it.min_stock or 0),
        })
    return {"items": items_page, "total": total, "page": page, "size": size}


@router.get(
    "/trend/{item_id}",
    summary="在庫推移（時系列）",
    description="指定商品の過去N日分の日次残高を返します（入庫-出庫±調整の累積）。",
)
def stock_trend(
    item_id: int,
    days: int = Query(30, ge=1, le=365),
    session: Session = Depends(get_session),
    t: Translator = Depends(get_translator),
):
    item = session.get(Item, item_id)
    if not item:
        raise HTTPException(404, t("errors.item_not_found"))
    from datetime import datetime, timedelta
    from collections import defaultdict

    end = datetime.utcnow().date()
    start = end - timedelta(days=days-1)

    # Movements up to end date
    rows = session.exec(
        select(StockMovement).where(StockMovement.item_id==item_id)
        .order_by(StockMovement.moved_at)
    ).all()

    # Starting balance before the start date
    start_balance = 0
    daily_delta = defaultdict(int)
    for m in rows:
        d = m.moved_at.date()
        delta = m.qty if m.type in ("IN","ADJUST") else -m.qty
        if d < start:
            start_balance += delta
        elif start <= d <= end:
            daily_delta[d] += delta

    # Build cumulative series
    series = []
    bal = start_balance
    cur = start
    from datetime import timedelta as _td
    while cur <= end:
        bal += daily_delta.get(cur, 0)
        series.append({"date": cur.isoformat(), "balance": bal, "delta": daily_delta.get(cur, 0)})
        cur = cur + _td(days=1)
    return {"item_id": item_id, "series": series}


@router.get(
    "/export/csv",
    summary="検索結果をCSVでエクスポート",
    description="/stock/search と同じパラメータで絞り込み、結果をCSVとしてダウンロードします（BOM付UTF-8既定）。",
)
def export_search_csv(
    q: str | None = Query(None),
    category: str | None = Query(None),
    low_only: bool = Query(False),
    min_balance: int | None = Query(None),
    max_balance: int | None = Query(None),
    sort_by: str = Query("id"),
    sort_dir: str = Query("asc"),
    encoding: str = Query("utf-8-sig"),
    session: Session = Depends(get_session),
):
    from sqlalchemy import func, case
    from sqlmodel import select

    bal_expr = func.sum(case((StockMovement.type == "IN", StockMovement.qty), (StockMovement.type == "OUT", -StockMovement.qty), else_=StockMovement.qty))
    bq = select(StockMovement.item_id, bal_expr.label("balance")).group_by(StockMovement.item_id).subquery("b")
    bal_col = func.coalesce(bq.c.balance, 0)

    base = select(
        Item.sku, Item.name, Item.category, Item.unit, Item.min_stock, bal_col.label("balance")
    ).select_from(Item).join(bq, bq.c.item_id == Item.id, isouter=True)

    if q:
        like = f"%{q}%"
        base = base.where((Item.sku.ilike(like)) | (Item.name.ilike(like)) | (Item.category.ilike(like)))
    if category:
        base = base.where(Item.category == category)
    if min_balance is not None:
        base = base.where(bal_col >= min_balance)
    if max_balance is not None:
        base = base.where(bal_col <= max_balance)
    if low_only:
        base = base.where(bal_col < func.coalesce(Item.min_stock, 0))

    # ordering
    keys = [k.strip() for k in sort_by.split(',') if k.strip()]
    dirs = [d.strip().lower() for d in sort_dir.split(',') if d.strip()]
    order_terms = []
    for idx, k in enumerate(keys or ["sku"]):
        direction = dirs[idx] if idx < len(dirs) else "asc"
        if k == "sku":
            col = Item.sku
        elif k == "name":
            col = Item.name
        elif k == "category":
            col = Item.category
        elif k == "unit":
            col = Item.unit
        elif k == "min_stock":
            col = Item.min_stock
        elif k == "balance":
            col = bal_col
        else:
            col = Item.sku
        order_terms.append(col.desc() if direction == "desc" else col.asc())
    base = base.order_by(*order_terms)

    res = session.exec(base).all()
    rows = [
        {
            "sku": sku,
            "name": name,
            "category": category or "",
            "unit": unit,
            "min_stock": min_stock,
            "balance": balance or 0,
        }
        for (sku, name, category, unit, min_stock, balance) in res
    ]

    from ..io_utils import dicts_to_csv
    content = dicts_to_csv(["sku","name","category","unit","min_stock","balance"], rows, encoding=encoding)
    filename = f"items_search_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv"
    headers = {"Content-Disposition": f"attachment; filename={filename}"}
    media = f"text/csv; charset={encoding}"
    return StreamingResponse(io.BytesIO(content), media_type=media, headers=headers)
