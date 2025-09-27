"""
Stock movement service for handling all stock-related operations with transaction support.
"""
from __future__ import annotations

import logging
from contextlib import contextmanager
from datetime import datetime, UTC
from typing import Dict, Optional, Tuple, List, Any, Generator, Type, TypeVar, cast

from sqlalchemy.exc import IntegrityError, SQLAlchemyError, OperationalError
from sqlalchemy import func
from sqlalchemy.orm.exc import StaleDataError
from sqlmodel import Session, select, or_

from ..models import StockMovement, Item
from ..exceptions import (
    InsufficientStockError,
    ItemNotFoundError,
    ConcurrentModificationError,
    DatabaseError
)
from ..schemas import StockIn, StockOut, StockAdjust, StockResponse
from .inventory import (
    compute_item_balance,
    record_stock_movement,
    get_item_with_lock,
)

# Configure logging
logger = logging.getLogger(__name__)

# Type variable for generic exception handling
T = TypeVar('T')

# Maximum retry attempts for optimistic locking
MAX_RETRIES = 3


class StockService:
    """Service class for stock management operations with transaction support."""
    
    def __init__(self, session: Session):
        """Initialize with a database session."""
        self.session = session
    
    @contextmanager
    def _transaction_context(self) -> Generator[None, None, None]:
        """Context manager for database transactions with error handling."""
        try:
            with self.session.begin():
                yield
        except IntegrityError as e:
            logger.error(f"Database integrity error: {str(e)}")
            self.session.rollback()
            if "unique constraint" in str(e).lower():
                raise ConcurrentModificationError("Concurrent modification detected") from e
            raise DatabaseError("Database integrity error") from e
        except StaleDataError as e:
            logger.warning(f"Optimistic lock error: {str(e)}")
            self.session.rollback()
            raise ConcurrentModificationError("The record was modified by another transaction") from e
        except OperationalError as e:
            logger.error(f"Database operational error: {str(e)}")
            self.session.rollback()
            raise DatabaseError("Database operation failed") from e
        except SQLAlchemyError as e:
            logger.error(f"Database error: {str(e)}")
            self.session.rollback()
            raise DatabaseError("Database operation failed") from e
        except Exception as e:
            logger.error(f"Unexpected error in transaction: {str(e)}")
            self.session.rollback()
            raise
    
    def _retry_on_conflict(self, operation: callable, *args, **kwargs) -> Any:
        """Retry operation on optimistic lock conflicts."""
        for attempt in range(MAX_RETRIES):
            try:
                with self._transaction_context():
                    return operation(*args, **kwargs)
            except ConcurrentModificationError:
                if attempt == MAX_RETRIES - 1:
                    raise
                logger.debug(f"Retry {attempt + 1}/{MAX_RETRIES} after conflict")
                continue
        raise ConcurrentModificationError("Maximum retry attempts reached")
    
    def _create_stock_movement(
        self,
        movement_type: str,
        item_id: int,
        qty: int,
        ref: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Tuple[StockMovement, float]:
        """Internal method to create a stock movement and return the movement and new balance."""
        item = get_item_with_lock(self.session, item_id)
        if not item:
            raise ItemNotFoundError(f"Item with ID {item_id} not found")
        
        # Create movement metadata
        movement_metadata = {
            "source": "api",
            "user": "system",
            **(metadata or {})
        }
        
        # Record the stock movement
        movement = record_stock_movement(
            session=self.session,
            movement_type=movement_type,
            item_id=item_id,
            qty=qty,
            ref=ref,
            metadata=movement_metadata
        )
        
        # Calculate new balance
        balance = compute_item_balance(self.session, item_id)
        
        return movement, balance
    
    def stock_in(self, payload: StockIn) -> StockResponse:
        """Record a stock in movement with transaction support.
        
        Args:
            payload: StockIn payload with item_id, qty, and optional ref
            
        Returns:
            StockResponse: The created stock movement with updated balance
            
        Raises:
            ItemNotFoundError: If the item doesn't exist
            ValueError: If the quantity is invalid
            DatabaseError: If a database error occurs
        """
        def _do_stock_in() -> Dict[str, Any]:
            movement, balance = self._create_stock_movement(
                movement_type="IN",
                item_id=payload.item_id,
                qty=payload.qty,
                ref=payload.ref
            )
            
            # Get the latest item version
            item = self.session.get(Item, payload.item_id)
            return {
                "id": movement.id,
                "item_id": movement.item_id,
                "type": movement.type,
                "qty": movement.qty,
                "ref": movement.ref,
                "moved_at": movement.moved_at,
                "balance": balance,
                "version": item.version if item else 0
            }
            
        return self._retry_on_conflict(_do_stock_in)
    
    def stock_out(self, payload: StockOut) -> StockResponse:
        """Record a stock out movement with transaction support.
        
        Args:
            payload: StockOut payload with item_id, qty, and optional ref
            
        Returns:
            StockResponse: The created stock movement with updated balance
            
        Raises:
            ItemNotFoundError: If the item doesn't exist
            InsufficientStockError: If there's not enough stock
            ValueError: If the quantity is invalid
            DatabaseError: If a database error occurs
        """
        def _do_stock_out() -> Dict[str, Any]:
            # Get item with lock first to prevent deadlocks
            item = get_item_with_lock(self.session, payload.item_id)
            if not item:
                raise ItemNotFoundError(f"Item with ID {payload.item_id} not found")
            
            # Check current balance with lock
            current_balance = compute_item_balance(self.session, payload.item_id, for_update=True)
            
            # Verify sufficient stock
            if current_balance < payload.qty:
                raise InsufficientStockError(
                    f"Insufficient stock. Current: {current_balance}, Requested: {payload.qty}"
                )
            
            # Record the stock movement
            movement, _ = self._create_stock_movement(
                movement_type="OUT",
                item_id=payload.item_id,
                qty=payload.qty,
                ref=payload.ref
            )
            
            # Calculate new balance
            new_balance = current_balance - payload.qty
            
            # Get the latest item version
            item = self.session.get(Item, payload.item_id)
            return {
                "id": movement.id,
                "item_id": movement.item_id,
                "type": movement.type,
                "qty": movement.qty,
                "ref": movement.ref,
                "moved_at": movement.moved_at,
                "balance": new_balance,
                "version": item.version if item else 0,
                "previous_balance": current_balance
            }
            
        return self._retry_on_conflict(_do_stock_out)
    
    def adjust_stock(self, payload: StockAdjust) -> StockResponse:
        """Record a stock adjustment with transaction support.
        
        Args:
            payload: StockAdjust payload with item_id, qty, and optional ref
            
        Returns:
            StockResponse: The created stock adjustment with updated balance
            
        Raises:
            ItemNotFoundError: If the item doesn't exist
            ValueError: If the quantity is invalid
            DatabaseError: If a database error occurs
        """
        def _do_adjust_stock() -> Dict[str, Any]:
            # Get item with lock first to prevent deadlocks
            item = get_item_with_lock(self.session, payload.item_id)
            if not item:
                raise ItemNotFoundError(f"Item with ID {payload.item_id} not found")
            
            # Get current balance with lock
            current_balance = compute_item_balance(self.session, payload.item_id, for_update=True)
            
            # Record the stock adjustment
            movement, _ = self._create_stock_movement(
                movement_type="ADJUST",
                item_id=payload.item_id,
                qty=payload.qty,
                ref=payload.ref,
                metadata={
                    "adjustment_reason": payload.ref or "manual_adjustment",
                    "previous_balance": current_balance
                }
            )
            
            # Calculate new balance
            new_balance = current_balance + payload.qty
            
            # Get the latest item version
            item = self.session.get(Item, payload.item_id)
            return {
                "id": movement.id,
                "item_id": movement.item_id,
                "type": movement.type,
                "qty": movement.qty,
                "ref": movement.ref,
                "moved_at": movement.moved_at,
                "balance": new_balance,
                "version": item.version if item else 0,
                "previous_balance": current_balance
            }
            
        return self._retry_on_conflict(_do_adjust_stock)
    
    def get_stock_balance(self, item_id: int) -> Dict[str, Any]:
        """Get the current stock balance for an item.
        
        Args:
            item_id: ID of the item
            
        Returns:
            Dict with balance information
            
        Raises:
            ItemNotFoundError: If the item doesn't exist
            DatabaseError: If a database error occurs
        """
        try:
            # Use read-committed isolation level for balance checks
            item = self.session.get(Item, item_id)
            if not item:
                raise ItemNotFoundError(f"Item with ID {item_id} not found")
            
            # Calculate balance without locking for better concurrency
            balance = compute_item_balance(self.session, item_id, for_update=False)
            
            return {
                "item_id": item_id,
                "balance": balance,
                "min_stock": item.min_stock,
                "needs_restock": balance <= item.min_stock,
                "unit": item.unit,
                "last_updated": datetime.now(UTC),
                "version": item.version
            }
            
        except SQLAlchemyError as e:
            logger.error(f"Error getting stock balance: {str(e)}")
            raise DatabaseError("Failed to get stock balance") from e
    
    def get_stock_movements(
        self,
        item_id: int,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        movement_type: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> Tuple[List[Dict[str, Any]], int]:
        """Get stock movements with filtering and pagination.
        
        Args:
            item_id: ID of the item
            start_date: Filter by movement date (>=)
            end_date: Filter by movement date (<=)
            movement_type: Filter by movement type (IN/OUT/ADJUST)
            limit: Maximum number of results (1-1000)
            offset: Number of results to skip
            
        Returns:
            Tuple of (movements, total_count)
            
        Raises:
            DatabaseError: If a database error occurs
        """
        try:
            # Validate limit to prevent excessive memory usage
            limit = max(1, min(limit, 1000))
            
            # Build base query
            query = select(StockMovement).where(StockMovement.item_id == item_id)
            count_query = select(func.count(StockMovement.id)).where(StockMovement.item_id == item_id)
            
            # Apply date filters
            if start_date:
                query = query.where(StockMovement.moved_at >= start_date)
                count_query = count_query.where(StockMovement.moved_at >= start_date)
                
            if end_date:
                # Add 1 day to include the end date
                end_date = end_date.replace(hour=23, minute=59, second=59, microsecond=999999)
                query = query.where(StockMovement.moved_at <= end_date)
                count_query = count_query.where(StockMovement.moved_at <= end_date)
                
            # Apply movement type filter
            if movement_type:
                movement_type = movement_type.upper()
                query = query.where(StockMovement.type == movement_type)
                count_query = count_query.where(StockMovement.type == movement_type)
            
            # Get total count first (without pagination)
            total = self.session.execute(count_query).scalar() or 0
            
            # Apply pagination and ordering
            query = (
                query
                .order_by(StockMovement.moved_at.desc())
                .offset(offset)
                .limit(limit)
            )
            
            # Execute query and format results
            movements = [
                {
                    "id": m.id,
                    "type": m.type,
                    "qty": float(m.qty),
                    "ref": m.ref,
                    "moved_at": m.moved_at.isoformat() if m.moved_at else None,
                    "metadata": m.meta or {}
                }
                for m in self.session.execute(query).scalars().all()
            ]
            
            return movements, total
            
        except SQLAlchemyError as e:
            logger.error(f"Error getting stock movements: {str(e)}")
            raise DatabaseError("Failed to get stock movements") from e
