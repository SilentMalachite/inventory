"""
Performance optimization utilities for the inventory system.
"""

import logging
from functools import wraps
from time import time
from typing import Any

from sqlalchemy import DDL
from sqlalchemy.exc import OperationalError
from sqlmodel import Session, func, select

from ..models import Item, StockMovement

logger = logging.getLogger(__name__)


def query_performance_threshold(threshold_seconds: float = 1.0):
    """Decorator to log slow queries."""

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time()
            result = func(*args, **kwargs)
            elapsed = time() - start_time

            if elapsed > threshold_seconds:
                logger.warning(
                    f"Slow query detected: {func.__name__} took {elapsed:.2f}s "
                    f"(threshold: {threshold_seconds}s)"
                )

            return result

        return wrapper

    return decorator


class BalanceCache:
    """Simple cache for stock balances to reduce database queries."""

    def __init__(self, ttl_seconds: int = 300):  # 5 minutes TTL
        self._cache: dict[int, tuple[float, int]] = (
            {}
        )  # {item_id: (timestamp, balance)}
        self._ttl = ttl_seconds

    def get(self, item_id: int) -> int | None:
        """Get cached balance if not expired."""
        if item_id in self._cache:
            timestamp, balance = self._cache[item_id]
            if time() - timestamp < self._ttl:
                return balance
            else:
                # Expired, remove from cache
                del self._cache[item_id]
        return None

    def set(self, item_id: int, balance: int) -> None:
        """Set cached balance."""
        self._cache[item_id] = (time(), balance)

    def invalidate(self, item_id: int) -> None:
        """Invalidate cache for specific item."""
        self._cache.pop(item_id, None)

    def clear(self) -> None:
        """Clear all cache."""
        self._cache.clear()


# Global balance cache instance
balance_cache = BalanceCache()


def get_cached_balance(
    session: Session, item_id: int, force_refresh: bool = False
) -> int:
    """Get balance with caching for better performance."""
    if not force_refresh:
        cached = balance_cache.get(item_id)
        if cached is not None:
            return cached

    # Calculate fresh balance
    from .inventory import compute_item_balance

    balance = compute_item_balance(session, item_id)

    # Cache the result
    balance_cache.set(item_id, balance)

    return balance


def invalidate_balance_cache(item_id: int) -> None:
    """Invalidate balance cache for an item."""
    balance_cache.invalidate(item_id)


def create_performance_indexes(engine) -> None:
    """Create additional indexes for better query performance."""
    try:
        with engine.connect() as conn:
            # Index for stock movement queries
            conn.execute(
                DDL(
                    """
                CREATE INDEX IF NOT EXISTS idx_stockmovement_item_type_moved_at
                ON stockmovement(item_id, type, moved_at)
            """
                )
            )

            # Index for stock movement balance calculations
            conn.execute(
                DDL(
                    """
                CREATE INDEX IF NOT EXISTS idx_stockmovement_item_qty_type
                ON stockmovement(item_id, qty, type)
            """
                )
            )

            # Index for item queries with category
            conn.execute(
                DDL(
                    """
                CREATE INDEX IF NOT EXISTS idx_item_category
                ON item(category)
            """
                )
            )

            # Index for item min_stock queries
            conn.execute(
                DDL(
                    """
                CREATE INDEX IF NOT EXISTS idx_item_min_stock
                ON item(min_stock)
            """
                )
            )

            conn.commit()
            logger.info("Performance indexes created successfully")

    except OperationalError as e:
        logger.warning(f"Failed to create performance indexes: {e}")


def optimize_database_settings(engine) -> None:
    """Apply database performance optimizations."""
    try:
        with engine.connect() as conn:
            # SQLite-specific optimizations
            if conn.dialect.name == "sqlite":
                optimizations = [
                    "PRAGMA journal_mode=WAL",
                    "PRAGMA synchronous=NORMAL",
                    "PRAGMA cache_size=10000",
                    "PRAGMA temp_store=MEMORY",
                    "PRAGMA mmap_size=268435456",  # 256MB
                    "PRAGMA busy_timeout=30000",
                    "PRAGMA foreign_keys=ON",
                ]

                for pragma in optimizations:
                    conn.execute(DDL(pragma))

                conn.commit()
                logger.info("Database optimizations applied")

    except Exception as e:
        logger.error(f"Failed to apply database optimizations: {e}")


def get_database_stats(session: Session) -> dict[str, Any]:
    """Get database statistics for monitoring."""
    try:
        stats = {}

        # Item count
        stats["item_count"] = session.exec(select(func.count(Item.id))).scalar()

        # Stock movement count
        stats["movement_count"] = session.exec(
            select(func.count(StockMovement.id))
        ).scalar()

        # Items with low stock
        low_stock_query = """
            SELECT COUNT(*)
            FROM item i
            LEFT JOIN (
                SELECT item_id,
                       SUM(CASE WHEN type = 'IN' THEN qty WHEN type = 'OUT' THEN -qty ELSE qty END) as balance
                FROM stockmovement
                GROUP BY item_id
            ) s ON i.id = s.item_id
            WHERE COALESCE(s.balance, 0) <= i.min_stock
        """
        result = session.exec(DDL(low_stock_query)).scalar()
        stats["low_stock_count"] = result if result else 0

        # Database size (if SQLite)
        if session.bind.dialect.name == "sqlite":
            try:
                db_size_query = "SELECT page_count * page_size as size FROM pragma_page_count(), pragma_page_size()"
                size_bytes = session.exec(DDL(db_size_query)).scalar()
                stats["db_size_bytes"] = size_bytes if size_bytes else 0
            except Exception:
                stats["db_size_bytes"] = 0

        return stats

    except Exception as e:
        logger.error(f"Failed to get database stats: {e}")
        return {"error": str(e)}
