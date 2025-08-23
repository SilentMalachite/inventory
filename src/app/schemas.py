from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


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

