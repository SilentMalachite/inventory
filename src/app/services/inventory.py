from __future__ import annotations

from typing import Dict, Iterable

from sqlmodel import Session, select
from sqlalchemy import func, case

from ..models import StockMovement


def compute_item_balance(session: Session, item_id: int) -> int:
    rows = session.exec(select(StockMovement).where(StockMovement.item_id == item_id)).all()
    total = 0
    for m in rows:
        if m.type == "IN":
            total += m.qty
        elif m.type == "OUT":
            total -= m.qty
        else:  # ADJUST
            total += m.qty
    return total


def compute_all_balances(session: Session) -> Dict[int, int]:
    rows = session.exec(select(StockMovement)).all()
    agg: Dict[int, int] = {}
    for m in rows:
        cur = agg.get(m.item_id, 0)
        if m.type == "IN":
            cur += m.qty
        elif m.type == "OUT":
            cur -= m.qty
        else:
            cur += m.qty
        agg[m.item_id] = cur
    return agg


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
