from __future__ import annotations

from typing import Dict, Iterable

from sqlmodel import Session, select
from sqlalchemy import func, case

from ..models import StockMovement


def compute_item_balance(session: Session, item_id: int) -> int:
    total_expr = func.sum(
        case(
            (StockMovement.type == "IN", StockMovement.qty),
            (StockMovement.type == "OUT", -StockMovement.qty),
            else_=StockMovement.qty,
        )
    )
    res = session.exec(
        select(total_expr).where(StockMovement.item_id == item_id)
    ).first()
    total_val = res[0] if isinstance(res, tuple) else res
    return int(total_val or 0)


def compute_all_balances(session: Session) -> Dict[int, int]:
    total_expr = func.sum(
        case(
            (StockMovement.type == "IN", StockMovement.qty),
            (StockMovement.type == "OUT", -StockMovement.qty),
            else_=StockMovement.qty,
        )
    )
    rows = session.exec(
        select(StockMovement.item_id, total_expr).group_by(StockMovement.item_id)
    ).all()
    return {item_id: int(total or 0) for (item_id, total) in rows}


def compute_balances_for_items(session: Session, item_ids: Iterable[int]) -> Dict[int, int]:
    ids = list({int(i) for i in item_ids if i is not None})
    if not ids:
        return {}
    total_expr = func.sum(
        case(
            (StockMovement.type == "IN", StockMovement.qty),
            (StockMovement.type == "OUT", -StockMovement.qty),
            else_=StockMovement.qty,
        )
    )
    rows = session.exec(
        select(StockMovement.item_id, total_expr).where(StockMovement.item_id.in_(ids)).group_by(StockMovement.item_id)
    ).all()
    return {item_id: (total or 0) for (item_id, total) in rows}
