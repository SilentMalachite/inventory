from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session

from ..db import get_session
from ..models import Item, StockMovement
from ..i18n import get_translator, Translator
from ..schemas import StockIn, StockOut, StockAdjust
from ..services.inventory import compute_item_balance, compute_all_balances
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
    stmt = select(Item)
    if q:
        like = f"%{q}%"
        stmt = stmt.where((Item.sku.ilike(like)) | (Item.name.ilike(like)) | (Item.category.ilike(like)))
    if category:
        stmt = stmt.where(Item.category == category)
    items = session.exec(stmt).all()
    balances = compute_all_balances(session)
    result = []
    for it in items:
        bal = balances.get(it.id or 0, 0)
        if min_balance is not None and bal < min_balance:
            continue
        if max_balance is not None and bal > max_balance:
            continue
        low = bal < (it.min_stock or 0)
        if low_only and not low:
            continue
        result.append({
            "id": it.id,
            "sku": it.sku,
            "name": it.name,
            "category": it.category,
            "unit": it.unit,
            "min_stock": it.min_stock,
            "balance": bal,
            "low": low,
        })
    total = len(result)
    keymap = {
        "id": lambda x: x["id"],
        "sku": lambda x: x["sku"] or "",
        "name": lambda x: x["name"] or "",
        "category": lambda x: x["category"] or "",
        "min_stock": lambda x: x["min_stock"],
        "balance": lambda x: x["balance"],
    }
    # support multi-key sort
    keys = [k.strip() for k in sort_by.split(',') if k.strip()]
    dirs = [d.strip().lower() for d in sort_dir.split(',') if d.strip()]
    # Apply stable sorts in reverse order for multi-key
    for idx in range(len(keys)-1, -1, -1):
        k = keys[idx] if idx < len(keys) else 'id'
        d = dirs[idx] if idx < len(dirs) else 'asc'
        key = keymap.get(k, keymap['id'])
        result.sort(key=key, reverse=(d=='desc'))
    start = (page-1)*size
    end = start + size
    items_page = result[start:end]
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
    # reuse search handler by calling internal logic (duplicate minimal code for simplicity)
    stmt = select(Item)
    if q:
        like = f"%{q}%"
        stmt = stmt.where((Item.sku.ilike(like)) | (Item.name.ilike(like)) | (Item.category.ilike(like)))
    if category:
        stmt = stmt.where(Item.category == category)
    items = session.exec(stmt).all()
    balances = compute_all_balances(session)
    rows = []
    for it in items:
        bal = balances.get(it.id or 0, 0)
        if min_balance is not None and bal < min_balance:
            continue
        if max_balance is not None and bal > max_balance:
            continue
        low = bal < (it.min_stock or 0)
        if low_only and not low:
            continue
        rows.append({
            "sku": it.sku,
            "name": it.name,
            "category": it.category or "",
            "unit": it.unit,
            "min_stock": it.min_stock,
            "balance": bal,
        })
    # sort
    keymap = {
        "sku": lambda x: x["sku"],
        "name": lambda x: x["name"],
        "category": lambda x: x["category"],
        "unit": lambda x: x["unit"],
        "min_stock": lambda x: x["min_stock"],
        "balance": lambda x: x["balance"],
    }
    keys = [k.strip() for k in sort_by.split(',') if k.strip()]
    dirs = [d.strip().lower() for d in sort_dir.split(',') if d.strip()]
    for idx in range(len(keys)-1, -1, -1):
        k = keys[idx] if idx < len(keys) else 'sku'
        d = dirs[idx] if idx < len(dirs) else 'asc'
        rows.sort(key=keymap.get(k, keymap['sku']), reverse=(d=='desc'))

    from ..io_utils import dicts_to_csv
    content = dicts_to_csv(["sku","name","category","unit","min_stock","balance"], rows, encoding=encoding)
    filename = f"items_search_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv"
    headers = {"Content-Disposition": f"attachment; filename={filename}"}
    media = f"text/csv; charset={encoding}"
    return StreamingResponse(io.BytesIO(content), media_type=media, headers=headers)
