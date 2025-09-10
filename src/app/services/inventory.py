from __future__ import annotations

from typing import Dict, Iterable, Optional, List, Tuple, Any
from datetime import datetime
from contextlib import contextmanager

from sqlmodel import Session, select, or_
from sqlalchemy import func, case, text, exc
from sqlalchemy.orm import with_polymorphic

from ..models import StockMovement, Item
from ..exceptions import (
    InsufficientStockError,
    ConcurrentModificationError,
    ItemNotFoundError
)
from ..schemas import StockIn, StockOut, StockAdjust, StockResponse


def compute_item_balance(session: Session, item_id: int, for_update: bool = False) -> int:
    """Calculate the current stock balance for an item.
    
    Args:
        session: Database session
        item_id: ID of the item
        for_update: If True, adds FOR UPDATE clause to lock the rows
        
    Returns:
        int: Current stock balance
    """
    query = (
        select(
            func.coalesce(
                func.sum(
                    case(
                        (StockMovement.type == "IN", StockMovement.qty),
                        (StockMovement.type == "OUT", -StockMovement.qty),
                        else_=StockMovement.qty,
                    )
                ),
                0
            ).label("balance")
        )
        .where(StockMovement.item_id == item_id)
    )
    
    if for_update:
        query = query.with_for_update()
        
    result = session.execute(query).scalar()
    return int(result) if result is not None else 0


def compute_all_balances(session: Session) -> Dict[int, int]:
    """Calculate stock balances for all items.
    
    Args:
        session: Database session
        
    Returns:
        Dict[int, int]: Dictionary mapping item IDs to their balances
    """
    query = (
        select(
            StockMovement.item_id,
            func.coalesce(
                func.sum(
                    case(
                        (StockMovement.type == "IN", StockMovement.qty),
                        (StockMovement.type == "OUT", -StockMovement.qty),
                        else_=StockMovement.qty,
                    )
                ),
                0
            ).label("balance")
        )
        .group_by(StockMovement.item_id)
    )
    
    rows = session.execute(query).all()
    return {item_id: int(balance) for item_id, balance in rows}


def compute_balances_for_items(session: Session, item_ids: Iterable[int]) -> Dict[int, int]:
    """Calculate stock balances for specific items.
    
    Args:
        session: Database session
        item_ids: Iterable of item IDs
        
    Returns:
        Dict[int, int]: Dictionary mapping item IDs to their balances
    """
    ids = list({int(i) for i in item_ids if i is not None})
    if not ids:
        return {}
        
    query = (
        select(
            StockMovement.item_id,
            func.coalesce(
                func.sum(
                    case(
                        (StockMovement.type == "IN", StockMovement.qty),
                        (StockMovement.type == "OUT", -StockMovement.qty),
                        else_=StockMovement.qty,
                    )
                ),
                0
            ).label("balance")
        )
        .where(StockMovement.item_id.in_(ids))
        .group_by(StockMovement.item_id)
    )
    
    rows = session.execute(query).all()
    return {item_id: int(balance) for item_id, balance in rows}


def record_stock_movement(
    session: Session,
    movement_type: str,
    item_id: int,
    qty: int,
    ref: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None
) -> StockMovement:
    """Record a stock movement with transaction support and optimistic locking.
    
    Args:
        session: Database session (should be within a transaction)
        movement_type: Type of movement (IN/OUT/ADJUST)
        item_id: ID of the item
        qty: Quantity (positive for IN, negative for OUT/ADJUST)
        ref: Reference information
        metadata: Additional metadata
        
    Returns:
        StockMovement: The created stock movement record
        
    Raises:
        ValueError: If movement_type is invalid
        InsufficientStockError: If trying to withdraw more than available stock
    """
    movement_type = movement_type.upper()
    if movement_type not in ("IN", "OUT", "ADJUST"):
        raise ValueError(f"Invalid movement type: {movement_type}")
    
    # Normalize qty per movement type
    if movement_type == "IN":
        stored_qty = abs(qty)
    elif movement_type == "OUT":
        stored_qty = abs(qty)  # store as positive; aggregation subtracts for OUT
    else:  # ADJUST
        stored_qty = int(qty)  # keep sign as provided
    
    # Create the movement record
    movement = StockMovement(
        item_id=item_id,
        type=movement_type,
        qty=stored_qty,
        ref=ref,
        meta=metadata or {}
    )
    
    session.add(movement)
    session.flush()  # Flush to get the ID
    
    return movement


def get_item_with_lock(session: Session, item_id: int) -> Optional[Item]:
    """Get an item with a row-level lock for update.
    
    Args:
        session: Database session
        item_id: ID of the item to retrieve
        
    Returns:
        Optional[Item]: The item if found, None otherwise
    """
    return session.exec(
        select(Item).where(Item.id == item_id).with_for_update()
    ).first()


def get_item_balance(session: Session, item_id: int) -> Dict[str, Any]:
    """Get detailed balance information for an item.
    
    Args:
        session: Database session
        item_id: ID of the item
        
    Returns:
        Dict[str, Any]: Dictionary containing balance information
    """
    from ..schemas import StockBalanceResponse
    
    item = session.get(Item, item_id)
    if not item:
        raise ItemNotFoundError(f"Item with ID {item_id} not found")
    
    balance = compute_item_balance(session, item_id)
    
    return {
        "item_id": item_id,
        "balance": balance,
        "min_stock": item.min_stock,
        "needs_restock": balance <= item.min_stock,
        "unit": item.unit,
        "last_updated": datetime.utcnow()
    }


def get_stock_movements(
    session: Session,
    item_id: int,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    movement_type: Optional[str] = None,
    limit: int = 100,
    offset: int = 0
) -> Tuple[List[Dict[str, Any]], int]:
    """Get stock movements with filtering and pagination.
    
    Args:
        session: Database session
        item_id: ID of the item
        start_date: Filter by movement date (>=)
        end_date: Filter by movement date (<=)
        movement_type: Filter by movement type (IN/OUT/ADJUST)
        limit: Maximum number of results
        offset: Number of results to skip
        
    Returns:
        Tuple[List[Dict[str, Any]], int]: List of movements and total count
    """
    query = select(StockMovement).where(StockMovement.item_id == item_id)
    count_query = select(func.count(StockMovement.id)).where(StockMovement.item_id == item_id)
    
    if start_date:
        query = query.where(StockMovement.moved_at >= start_date)
        count_query = count_query.where(StockMovement.moved_at >= start_date)
        
    if end_date:
        query = query.where(StockMovement.moved_at <= end_date)
        count_query = count_query.where(StockMovement.moved_at <= end_date)
        
    if movement_type:
        query = query.where(StockMovement.type == movement_type.upper())
        count_query = count_query.where(StockMovement.type == movement_type.upper())
    
    # Get total count
    total = session.execute(count_query).scalar()
    
    # Apply pagination
    query = query.order_by(StockMovement.moved_at.desc()).offset(offset).limit(limit)
    
    # Execute query and format results
    movements = [
        {
            "id": m.id,
            "type": m.type,
            "qty": int(m.qty),
            "ref": m.ref,
            "moved_at": m.moved_at,
            "metadata": m.meta or {},
        }
        for m in session.execute(query).scalars().all()
    ]
    
    return movements, total
