"""
Custom exceptions for the inventory system.
"""
from fastapi import status, HTTPException
from typing import Optional, Dict, Any


class InventoryError(HTTPException):
    """Base exception for inventory related errors"""
    status_code = status.HTTP_400_BAD_REQUEST
    detail = "An error occurred"
    
    def __init__(
        self, 
        detail: Optional[str] = None, 
        status_code: Optional[int] = None,
        headers: Optional[Dict[str, str]] = None,
        **extras: Any
    ) -> None:
        self.detail = detail or self.detail
        self.status_code = status_code or self.status_code
        self.extras = extras
        super().__init__(
            status_code=self.status_code, 
            detail=self.detail,
            headers=headers
        )


class ItemNotFoundError(InventoryError):
    """Raised when an item is not found"""
    status_code = status.HTTP_404_NOT_FOUND
    detail = "Item not found"


class InsufficientStockError(InventoryError):
    """Raised when there is not enough stock to fulfill a request"""
    status_code = status.HTTP_400_BAD_REQUEST
    detail = "Insufficient stock"


class ConcurrentModificationError(InventoryError):
    """Raised when a concurrent modification is detected"""
    status_code = status.HTTP_409_CONFLICT
    detail = "The resource has been modified by another process"


class DatabaseError(InventoryError):
    """Raised when a generic database error occurs"""
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    detail = "Database operation failed"


def handle_api_errors(func):
    """
    Decorator to handle common API errors and convert them to appropriate HTTP responses.
    """
    from functools import wraps
    from sqlalchemy.exc import IntegrityError, SQLAlchemyError
    
    @wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs) if hasattr(func, '__await__') else func(*args, **kwargs)
        except InventoryError as e:
            raise e
        except IntegrityError as e:
            if "foreign key" in str(e).lower():
                raise ItemNotFoundError("The referenced item does not exist") from e
            if "unique" in str(e).lower():
                raise InventoryError("A duplicate entry already exists", status.HTTP_409_CONFLICT) from e
            raise InventoryError("Database integrity error") from e
        except SQLAlchemyError as e:
            raise InventoryError("Database error") from e
        except Exception as e:
            raise InventoryError(str(e)) from e
    
    return wrapper
