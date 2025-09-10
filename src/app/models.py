from __future__ import annotations

from datetime import datetime, UTC
from typing import Optional, Any, Dict

from sqlmodel import Field, SQLModel, Column
from sqlalchemy import DateTime, String, CheckConstraint, event, JSON
from sqlalchemy.orm import Session


class BaseModel(SQLModel):
    """Base model with common fields and methods"""
    version: int = Field(default=0, description="楽観的ロック用バージョン")

    def increment_version(self):
        """Increment the version number for optimistic locking"""
        self.version += 1
        return self.version


class Item(BaseModel, table=True):
    """商品モデル"""
    id: Optional[int] = Field(default=None, primary_key=True, description="商品ID")
    sku: str = Field(index=True, unique=True, description="SKU（商品コード）")
    name: str = Field(description="商品名")
    category: Optional[str] = Field(default=None, description="カテゴリ")
    unit: str = Field(default="pcs", description="単位")
    min_stock: int = Field(default=0, ge=0, description="最低在庫数")
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        # Python 側で一貫して UTC の aware datetime を設定する
        sa_column=Column(DateTime(timezone=True), nullable=False),
        description="作成日時(UTC)"
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        # onupdate の DB 側デフォルトは使わず、アプリ側で更新（例: update_item）
        sa_column=Column(DateTime(timezone=True), nullable=False),
        description="更新日時(UTC)",
    )

    # Relationship fields are omitted for simplicity of schema/docs


class StockMovement(BaseModel, table=True):
    """在庫移動モデル"""
    id: Optional[int] = Field(default=None, primary_key=True, description="在庫移動ID")
    item_id: int = Field(foreign_key="item.id", index=True, description="商品ID")
    type: str = Field(
        description='種別（"IN"|"OUT"|"ADJUST"）',
        sa_column=Column(String(10), CheckConstraint("type IN ('IN','OUT','ADJUST')", name="ck_stockmovement_type"), nullable=False),
    )
    qty: int = Field(description="数量")
    ref: Optional[str] = Field(default=None, max_length=255, description="参照情報")
    meta: Dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSON, nullable=False, default=dict),
        description="Additional metadata as JSON"
    )
    moved_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        sa_column=Column(DateTime(timezone=True), nullable=False, index=True),
        description="移動日時(UTC)"
    )

# 楽観的ロックのためのイベントリスナーを設定
@event.listens_for(Item, 'before_update')
def receive_before_update(mapper, connection, target):
    """更新前にバージョン番号をインクリメント"""
    target.increment_version()


# 在庫移動時の整合性チェック
@event.listens_for(StockMovement, 'before_insert')
def check_stock_balance(mapper, connection, target):
    """在庫移動前に在庫残高をチェック"""
    if target.type == 'OUT':
        # 出庫の場合は在庫残高をチェック
        session = Session.object_session(target)
        if session:
            from .services.inventory import compute_item_balance
            current_balance = compute_item_balance(session, target.item_id)
            if current_balance < target.qty:
                raise ValueError(f"在庫が不足しています。現在の在庫: {current_balance}, 出庫要求: {target.qty}")


@event.listens_for(Session, 'after_flush')
def validate_stock_balance(session: Session, context):
    """フラッシュ後に在庫残高がマイナスになっていないか検証"""
    from .services.inventory import compute_item_balance

    for instance in session.dirty.union(session.new):
        if isinstance(instance, StockMovement):
            balance = compute_item_balance(session, instance.item_id)
            if balance < 0:
                raise ValueError(f"在庫がマイナスになります。商品ID: {instance.item_id}, 在庫数: {balance}")
