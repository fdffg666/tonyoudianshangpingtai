# models/cart.py
from sqlalchemy import Column, Integer, ForeignKey, DateTime, UniqueConstraint, Index
from sqlalchemy.orm import relationship
from datetime import datetime
from models.base import Base
from models.user import User

class Cart(Base):
    """购物车主表"""
    __tablename__ = "carts"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="购物车ID")
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True, comment="用户ID")
    created_at = Column(DateTime, default=datetime.now, comment="创建时间")
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment="更新时间")

    # 关系
    user = relationship(User)
    items = relationship("CartItem", back_populates="cart", cascade="all, delete-orphan")


class CartItem(Base):
    """购物车明细表"""
    __tablename__ = "cart_items"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="明细ID")
    cart_id = Column(Integer, ForeignKey("carts.id", ondelete="CASCADE"), nullable=False, comment="购物车ID")
    product_id = Column(Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=False, comment="商品ID")
    quantity = Column(Integer, nullable=False, default=1, comment="商品数量")
    added_at = Column(DateTime, default=datetime.now, comment="加入时间")

    # 关系
    cart = relationship("Cart", back_populates="items")
    product = relationship("Product")  # 用于联查商品信息

    __table_args__ = (
        UniqueConstraint("cart_id", "product_id", name="uk_cart_product"),
        Index("idx_product_id", "product_id"),
    )