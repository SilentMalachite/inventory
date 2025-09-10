from __future__ import annotations
from datetime import datetime
from typing import Optional, Dict, Any, TypeVar, Generic
from pydantic import BaseModel, Field, field_validator, ConfigDict

# Generic type for response data
T = TypeVar('T')

class BaseResponse(BaseModel, Generic[T]):
    """Base response model for all API responses"""
    success: bool = True
    data: T
    error: Optional[str] = None
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "data": {},
                "error": None
            }
        }
    )


class ErrorResponse(BaseModel):
    """Standard error response model"""
    success: bool = False
    error: str
    details: Optional[Dict[str, Any]] = None
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": False,
                "error": "Error message",
                "details": {"field": "error details"}
            }
        }
    )


class ItemCreate(BaseModel):
    sku: str = Field(..., description="SKU（商品コード）")
    name: str = Field(..., description="商品名")
    category: str | None = Field(None, description="カテゴリ")
    unit: str = Field("pcs", description="単位")
    min_stock: int = Field(0, ge=0, description="最低在庫数")


class ItemUpdate(BaseModel):
    name: str | None = Field(None, description="商品名")
    category: str | None = Field(None, description="カテゴリ")
    unit: str | None = Field(None, description="単位")
    min_stock: int | None = Field(None, ge=0, description="最低在庫数")


class StockIn(BaseModel):
    item_id: int = Field(..., description="商品ID")
    qty: int = Field(..., gt=0, description="入庫数（正の整数）")
    ref: str | None = Field(None, description="参照情報")


class StockOut(BaseModel):
    item_id: int = Field(..., description="商品ID")
    qty: int = Field(..., gt=0, description="出庫数（正の整数）")
    ref: str | None = Field(None, description="参照情報")


class StockAdjust(BaseModel):
    item_id: int = Field(..., description="商品ID")
    qty: int = Field(..., description="調整数（正負可、0不可）")
    ref: str | None = Field(None, description="参照情報")

    @field_validator("qty")
    @classmethod
    def non_zero(cls, v: int) -> int:
        if v == 0:
            raise ValueError("0は指定できません")
        return v


class StockResponse(BaseModel):
    """Response model for stock operations"""
    id: int = Field(..., description="在庫移動ID")
    item_id: int = Field(..., description="商品ID")
    type: str = Field(..., description="種別（IN/OUT/ADJUST）")
    qty: int = Field(..., description="数量")
    ref: Optional[str] = Field(None, description="参照情報")
    moved_at: datetime = Field(..., description="移動日時")
    balance: int = Field(..., description="更新後の在庫残高")
    version: int = Field(..., description="バージョン番号（楽観的ロック用）")
    previous_balance: Optional[int] = Field(None, description="更新前の在庫残高（調整時のみ）")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": 1,
                "item_id": 1,
                "type": "IN",
                "qty": 10,
                "ref": "PO123",
                "moved_at": "2023-01-01T00:00:00Z",
                "balance": 10,
                "version": 1,
                "previous_balance": 0
            }
        }
    )


class StockBalanceResponse(BaseModel):
    """Response model for stock balance queries"""
    item_id: int = Field(..., description="商品ID")
    balance: int = Field(..., description="現在の在庫数")
    min_stock: int = Field(..., description="最低在庫数")
    needs_restock: bool = Field(..., description="発注が必要かどうか")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "item_id": 1,
                "balance": 5,
                "min_stock": 10,
                "needs_restock": True
            }
        }
    )


class ItemResponse(BaseModel):
    """Response model for item operations"""
    id: int = Field(..., description="商品ID")
    sku: str = Field(..., description="SKU（商品コード）")
    name: str = Field(..., description="商品名")
    category: Optional[str] = Field(None, description="カテゴリ")
    unit: str = Field(..., description="単位")
    min_stock: int = Field(..., description="最低在庫数")
    created_at: datetime = Field(..., description="作成日時")
    updated_at: datetime = Field(..., description="更新日時")
    version: int = Field(..., description="バージョン番号（楽観的ロック用）")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": 1,
                "sku": "ITEM-001",
                "name": "サンプル商品",
                "category": "一般",
                "unit": "個",
                "min_stock": 10,
                "created_at": "2023-01-01T00:00:00Z",
                "updated_at": "2023-01-01T00:00:00Z",
                "version": 1
            }
        }
    )
