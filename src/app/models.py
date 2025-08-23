from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel
from sqlalchemy import Column, DateTime, String, CheckConstraint


class Item(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True, description="商品ID")
    sku: str = Field(index=True, unique=True, description="SKU（商品コード）")
    name: str = Field(description="商品名")
    category: Optional[str] = Field(default=None, description="カテゴリ")
    unit: str = Field(default="pcs", description="単位")
    min_stock: int = Field(default=0, description="最低在庫数")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="作成日時(UTC)")
    updated_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="更新日時(UTC)",
        sa_column=Column(DateTime, onupdate=datetime.utcnow),
    )

    # Relationship fields are omitted for simplicity of schema/docs


class StockMovement(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True, description="在庫移動ID")
    item_id: int = Field(foreign_key="item.id", index=True, description="商品ID")
    type: str = Field(
        description='種別（"IN"|"OUT"|"ADJUST"）',
        sa_column=Column(String, CheckConstraint("type IN ('IN','OUT','ADJUST')", name="ck_stockmovement_type")),
    )
    qty: int = Field(description="数量")
    ref: Optional[str] = Field(default=None, description="参照情報")
    moved_at: datetime = Field(default_factory=datetime.utcnow, description="移動日時(UTC)")

    # Relationship backref omitted
