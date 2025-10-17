import io
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import JSONResponse, StreamingResponse
from sqlmodel import Session, select
from starlette.concurrency import run_in_threadpool

from ..audit import audit
from ..db import get_session
from ..exceptions import handle_api_errors
from ..i18n import Translator, get_translator
from ..io_utils import items_to_csv, items_to_xlsx, parse_items_csv, parse_items_xlsx
from ..models import Item, StockMovement
from ..schemas import ItemCreate, ItemUpdate

router = APIRouter()


@router.post(
    "/",
    response_model=Item,
    status_code=201,
    summary="商品を登録",
    description="SKUが一意になるように商品を作成します。",
)
@handle_api_errors
def create_item(
    item: ItemCreate,
    session: Session = Depends(get_session),
    t: Translator = Depends(get_translator),  # noqa: ARG001
):
    obj = Item(**item.model_dump())
    session.add(obj)
    session.commit()
    session.refresh(obj)
    audit("item.create", id=obj.id, sku=obj.sku, name=obj.name)
    return obj


@router.get(
    "/",
    response_model=list[Item],
    summary="商品一覧を取得",
    description="登録済みの商品をすべて返します。",
)
def list_items(
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
    session: Session = Depends(get_session),
):
    stmt = select(Item).offset((page - 1) * size).limit(size)
    return session.exec(stmt).all()


@router.get(
    "/{item_id}",
    response_model=Item,
    summary="商品を取得",
    description="指定したIDの商品を返します。",
)
@handle_api_errors
def get_item(
    item_id: int,
    session: Session = Depends(get_session),
    t: Translator = Depends(get_translator),
):
    item = session.get(Item, item_id)
    if not item:
        raise HTTPException(status_code=404, detail=t("errors.item_not_found"))
    return item


@router.put(
    "/{item_id}",
    response_model=Item,
    summary="商品を更新",
    description="指定したIDの商品情報を更新します。",
)
@handle_api_errors
def update_item(
    item_id: int,
    payload: ItemUpdate,
    session: Session = Depends(get_session),
    t: Translator = Depends(get_translator),
):
    item = session.get(Item, item_id)
    if not item:
        raise HTTPException(status_code=404, detail=t("errors.item_not_found"))
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(item, key, value)
    # update timestamp
    item.updated_at = datetime.now(UTC)
    session.add(item)
    session.commit()
    session.refresh(item)
    audit("item.update", id=item.id)
    return item


@router.delete(
    "/{item_id}",
    status_code=204,
    summary="商品を削除",
    description="指定したIDの商品を削除します。",
)
@handle_api_errors
def delete_item(
    item_id: int,
    session: Session = Depends(get_session),
    t: Translator = Depends(get_translator),
):
    item = session.get(Item, item_id)
    if not item:
        raise HTTPException(status_code=404, detail=t("errors.item_not_found"))
    # Delete dependent stock movements first to satisfy FK constraints
    moves = session.exec(
        select(StockMovement).where(StockMovement.item_id == item_id)
    ).all()
    for m in moves:
        session.delete(m)
    session.delete(item)
    session.commit()
    audit("item.delete", id=item_id)
    return None


@router.get(
    "/categories",
    summary="カテゴリ一覧を取得",
    description="登録済み商品のカテゴリを重複なく返します（nullは除外）。",
    response_model=list[str],
)
def list_categories(session: Session = Depends(get_session)):
    rows = session.exec(
        select(Item.category)
        .where(Item.category.is_not(None))
        .distinct()
        .order_by(Item.category)
    ).all()
    return [r for (r,) in rows if r]


@router.post(
    "/categories/rename",
    summary="カテゴリ名を一括変更",
    description="from で指定したカテゴリ名を to へ一括変更します。",
)
def rename_category(
    payload: dict,
    session: Session = Depends(get_session),
):
    src = (payload.get("from") or "").strip()
    dst = (payload.get("to") or "").strip()
    if not src or not dst:
        return JSONResponse(
            status_code=400, content={"detail": "from/to を指定してください"}
        )
    items = session.exec(select(Item).where(Item.category == src)).all()
    for it in items:
        it.category = dst
        session.add(it)
    session.commit()
    return {"updated": len(items)}


@router.post(
    "/categories/delete",
    summary="カテゴリの一括削除",
    description="指定カテゴリを全商品から外します（category を null に設定）。",
)
def delete_category(
    payload: dict,
    session: Session = Depends(get_session),
):
    cat = (payload.get("category") or "").strip()
    if not cat:
        return JSONResponse(
            status_code=400, content={"detail": "category を指定してください"}
        )
    items = session.exec(select(Item).where(Item.category == cat)).all()
    for it in items:
        it.category = None
        session.add(it)
    session.commit()
    return {"updated": len(items)}


@router.get(
    "/export/csv",
    summary="商品をCSVでエクスポート",
    description="Windows Excelで文字化けしないようUTF-8 BOM（utf-8-sig）を既定とします。",
)
def export_items_csv(
    encoding: str = Query("utf-8-sig", description="utf-8-sig または cp932 を推奨"),
    session: Session = Depends(get_session),
):
    items = session.exec(select(Item)).all()
    content = items_to_csv(items, encoding=encoding)
    filename = f"items_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}.csv"
    headers = {
        "Content-Disposition": f"attachment; filename={filename}",
    }
    media = f"text/csv; charset={encoding}"
    return StreamingResponse(io.BytesIO(content), media_type=media, headers=headers)


@router.get(
    "/export/xlsx",
    summary="商品をExcelでエクスポート",
    description="拡張子 .xlsx のファイルを返します。",
)
def export_items_xlsx(session: Session = Depends(get_session)):
    items = session.exec(select(Item)).all()
    content = items_to_xlsx(items)
    filename = f"items_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}.xlsx"
    headers = {
        "Content-Disposition": f"attachment; filename={filename}",
    }
    return StreamingResponse(
        io.BytesIO(content),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers=headers,
    )


@router.post(
    "/import/csv",
    summary="CSVから商品を取り込み",
    description="ヘッダー行が必要です（sku,name,category,unit,min_stock）。エンコードは utf-8-sig または cp932 を推奨。",
)
async def import_items_csv(
    file: UploadFile = File(...),
    encoding: str | None = Query(
        None, description="明示する場合は utf-8-sig か cp932 を指定"
    ),
    session: Session = Depends(get_session),
    t: Translator = Depends(get_translator),  # noqa: ARG001
):
    data = await file.read()
    try:
        rows = await run_in_threadpool(parse_items_csv, data, encoding)
    except Exception as e:
        return JSONResponse(status_code=400, content={"detail": str(e)})
    inserted = 0
    updated = 0

    # DB-heavy loop in threadpool to avoid blocking event loop
    def _upsert_rows():
        nonlocal inserted, updated
        for r in rows:
            sku = r["sku"]
            if not sku or not r["name"]:
                continue
            existing = session.exec(select(Item).where(Item.sku == sku)).first()
            if existing:
                for k in ("name", "category", "unit", "min_stock"):
                    setattr(existing, k, r[k])
                session.add(existing)
                updated += 1
            else:
                obj = Item(**r)
                session.add(obj)
                inserted += 1
        session.commit()

    await run_in_threadpool(_upsert_rows)
    audit("item.import.csv", inserted=inserted, updated=updated)
    return {"inserted": inserted, "updated": updated}


@router.post(
    "/import/xlsx",
    summary="Excelから商品を取り込み",
    description="ヘッダー行（sku,name,category,unit,min_stock）が必要です。",
)
async def import_items_xlsx(
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
    t: Translator = Depends(get_translator),  # noqa: ARG001
):
    data = await file.read()
    try:
        rows = await run_in_threadpool(parse_items_xlsx, data)
    except Exception as e:
        return JSONResponse(status_code=400, content={"detail": str(e)})
    inserted = 0
    updated = 0

    def _upsert_rows():
        nonlocal inserted, updated
        for r in rows:
            sku = r["sku"]
            if not sku or not r["name"]:
                continue
            existing = session.exec(select(Item).where(Item.sku == sku)).first()
            if existing:
                for k in ("name", "category", "unit", "min_stock"):
                    setattr(existing, k, r[k])
                session.add(existing)
                updated += 1
            else:
                obj = Item(**r)
                session.add(obj)
                inserted += 1
        session.commit()

    await run_in_threadpool(_upsert_rows)
    audit("item.import.xlsx", inserted=inserted, updated=updated)
    return {"inserted": inserted, "updated": updated}
