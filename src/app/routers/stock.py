from fastapi import APIRouter, Depends, HTTPException, Query, status, Response
from fastapi.responses import StreamingResponse, JSONResponse
from datetime import datetime, UTC
import io
from typing import Optional, List, Dict, Any

from sqlmodel import Session, select

from ..db import get_session
from ..i18n import get_translator, Translator
from ..schemas import (
    StockIn,
    StockOut,
    StockAdjust,
    StockResponse,
    ErrorResponse,
)
from ..models import Item, StockMovement
from ..services.stock_service import StockService
from ..audit import audit
from ..exceptions import handle_api_errors
from ..services.inventory import compute_all_balances

router = APIRouter()


@router.post(
    "/in",
    response_model=StockResponse,
    status_code=status.HTTP_201_CREATED,
    summary="入庫を登録",
    description="指定した商品に対する入庫を記録します。",
    responses={
        404: {"model": ErrorResponse, "description": "商品が見つからない場合"},
        409: {"model": ErrorResponse, "description": "楽観的ロックの競合が発生した場合"},
        400: {"model": ErrorResponse, "description": "バリデーションエラー"},
    }
)
@handle_api_errors
def stock_in(
    payload: StockIn,
    session: Session = Depends(get_session),
    t: Translator = Depends(get_translator),
):
    """在庫入庫を記録します。
    
    追加仕様:
    - qty が 0 の場合は 422 を返す
    - qty が 負 の場合:
      - 対象商品が存在すれば、出庫として処理（/stock/out 相当）
      - 対象商品が存在しない場合は 422 を返す（バリデーションエラー互換）
    
    Args:
        payload: 入庫情報
        session: データベースセッション
        t: 翻訳関数
        
    Returns:
        BaseResponse[StockResponse]: 登録された在庫移動情報
    """
    # 0 は不可
    if payload.qty == 0:
        raise HTTPException(status_code=422, detail=t("errors.validation_failed"))
    
    # 負数は出庫として扱う（ただし商品が存在しない場合は 422）
    if payload.qty < 0:
        item = session.get(Item, payload.item_id)
        if not item:
            # バリデーションエラー扱い（テスト期待に合わせる）
            raise HTTPException(status_code=422, detail=t("errors.validation_failed"))
        # 出庫として処理
        stock_service = StockService(session)
        out_payload = StockOut(item_id=payload.item_id, qty=abs(payload.qty), ref=payload.ref)
        result = stock_service.stock_out(out_payload)
        audit(
            "stock.out",
            item_id=payload.item_id,
            qty=abs(payload.qty),
            ref=payload.ref,
            version=result["version"],
        )
        return result

    # 正の数は通常の入庫
    stock_service = StockService(session)
    result = stock_service.stock_in(payload)
    
    # 監査ログ
    audit(
        "stock.in",
        item_id=payload.item_id,
        qty=payload.qty,
        ref=payload.ref,
        version=result["version"]
    )
    
    return result


@router.post(
    "/out",
    response_model=StockResponse,
    status_code=status.HTTP_201_CREATED,
    summary="出庫を登録",
    description="指定した商品に対する出庫を記録します。在庫が不足している場合はエラーになります。",
    responses={
        404: {"model": ErrorResponse, "description": "商品が見つからない場合"},
        400: {"model": ErrorResponse, "description": "在庫が不足している場合"},
        409: {"model": ErrorResponse, "description": "楽観的ロックの競合が発生した場合"},
    }
)
@handle_api_errors
def stock_out(
    payload: StockOut,
    session: Session = Depends(get_session),
    t: Translator = Depends(get_translator),
):
    """在庫出庫を記録します。
    
    Args:
        payload: 出庫情報
        session: データベースセッション
        t: 翻訳関数
        
    Returns:
        BaseResponse[StockResponse]: 登録された在庫移動情報
        
    Raises:
        HTTPException: 商品が見つからない場合、在庫不足、または楽観的ロックエラーが発生した場合
    """
    stock_service = StockService(session)
    result = stock_service.stock_out(payload)
    
    # 監査ログ
    audit(
        "stock.out",
        item_id=payload.item_id,
        qty=payload.qty,
        ref=payload.ref,
        version=result["version"]
    )
    
    return result


@router.post(
    "/adjust",
    response_model=StockResponse,
    status_code=status.HTTP_201_CREATED,
    summary="在庫調整を登録",
    description="実在庫との差異を調整として記録します（正負可、0不可）。",
    responses={
        404: {"model": ErrorResponse, "description": "商品が見つからない場合"},
        400: {"model": ErrorResponse, "description": "調整数量が0の場合"},
        409: {"model": ErrorResponse, "description": "楽観的ロックの競合が発生した場合"},
    }
)
@handle_api_errors
def stock_adjust(
    payload: StockAdjust,
    session: Session = Depends(get_session),
    t: Translator = Depends(get_translator),
):
    """在庫調整を記録します。
    
    Args:
        payload: 調整情報
        session: データベースセッション
        t: 翻訳関数
        
    Returns:
        BaseResponse[StockResponse]: 登録された在庫調整情報
    """
    stock_service = StockService(session)
    result = stock_service.adjust_stock(payload)
    
    # 監査ログ
    audit(
        "stock.adjust",
        item_id=payload.item_id,
        qty=payload.qty,
        ref=payload.ref,
        version=result["version"],
        metadata={"previous_balance": result.get("previous_balance")}
    )
    
    return result


@router.get(
    "/balance/{item_id}",
    summary="在庫残高を取得",
    description="指定した商品の現在の在庫数と在庫ステータスを取得します。",
    responses={
        404: {"model": ErrorResponse, "description": "商品が見つからない場合"}
    }
)
@handle_api_errors
def get_balance(
    item_id: int,
    session: Session = Depends(get_session),
    t: Translator = Depends(get_translator)
):
    """指定した商品の在庫残高を取得します。
    
    Args:
        item_id: 商品ID
        session: データベースセッション
        t: 翻訳関数
        
    Returns:
        BaseResponse[StockBalanceResponse]: 在庫残高情報
    """
    stock_service = StockService(session)
    balance_info = stock_service.get_stock_balance(item_id)
    return balance_info


@router.get(
    "/balances",
    summary="全商品の在庫残高一覧を取得",
    description="登録されている全商品の在庫残高を返します。",
)
@handle_api_errors
async def get_all_balances(
    session: Session = Depends(get_session)
):
    """全商品の在庫残高を取得します。
    
    Args:
        session: データベースセッション
        
    Returns:
        BaseResponse[List[Dict[str, Any]]]: 全商品の在庫残高リスト
    """
    balances = compute_all_balances(session)
    return [{"item_id": k, "balance": v} for k, v in balances.items()]


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
    # Retrieve count in a way that works across SQLAlchemy/SQLModel versions
    _res = session.exec(count_stmt)
    if isinstance(_res, int):
        total = _res
    elif hasattr(_res, "one"):
        _val = _res.one()
        total = _val[0] if isinstance(_val, (tuple, list)) else int(_val)
    elif hasattr(_res, "scalar_one"):
        total = int(_res.scalar_one())
    else:
        # Fallback: try to cast to int
        total = int(_res)

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

    end = datetime.now(UTC).date()
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
    # Return as 'trend' to match API contract in tests
    return {"item_id": item_id, "trend": series}


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
    filename = f"items_search_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}.csv"
    headers = {"Content-Disposition": f"attachment; filename={filename}"}
    media = f"text/csv; charset={encoding}"
    return StreamingResponse(io.BytesIO(content), media_type=media, headers=headers)
