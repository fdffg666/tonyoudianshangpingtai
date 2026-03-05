# models/order.py
from sqlalchemy import Column, Integer, String, DECIMAL, DateTime, Date, Enum, ForeignKey, Index, Text
from sqlalchemy.orm import relationship
from datetime import datetime
import enum

from models.base import Base  # 假设已统一 Base


class OrderStatus(str, enum.Enum):
    PENDING = "pending"      # 待确认
    CONFIRMED = "confirmed"  # 已确认
    SHIPPED = "shipped"      # 已发货
    COMPLETED = "completed"  # 已完成
    CANCELLED = "cancelled"  # 已取消


class Order(Base):
    """订单主表"""
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, autoincrement=True)
    order_no = Column(String(32), unique=True, nullable=False, comment="订单号")
    user_id = Column(Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    total_amount = Column(DECIMAL(10, 2), nullable=False, default=0.00)
    status = Column(String(20), nullable=False, default=OrderStatus.PENDING.value)
    expected_delivery_date = Column(Date, nullable=True)
    remark = Column(String(500), nullable=True)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    # 关系
    user = relationship("User")
    items = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_user_id", "user_id"),
        Index("idx_status", "status"),
        Index("idx_created_at", "created_at"),
    )


class OrderItem(Base):
    """订单明细表"""
    __tablename__ = "order_items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    order_id = Column(Integer, ForeignKey("orders.id", ondelete="CASCADE"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id", ondelete="RESTRICT"), nullable=False)
    quantity = Column(Integer, nullable=False)
    price = Column(DECIMAL(10, 2), nullable=False, comment="下单时单价")
    subtotal = Column(DECIMAL(10, 2), nullable=False, comment="小计")
    created_at = Column(DateTime, default=datetime.now)

    # 关系
    order = relationship("Order", back_populates="items")
    product = relationship("Product")  # 用于获取商品快照以外的信息

    __table_args__ = (
        Index("idx_order_id", "order_id"),
        Index("idx_product_id", "product_id"),
    )