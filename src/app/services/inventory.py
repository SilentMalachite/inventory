from __future__ import annotations

from typing import Dict

from sqlmodel import Session, select

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

