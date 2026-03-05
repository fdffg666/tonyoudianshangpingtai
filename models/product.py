# models/product.py
from sqlalchemy import Column, Integer, String, Float, DateTime, Text, Index
from datetime import datetime
from models.base import Base


class Product(Base):
    """商品主表"""
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="商品ID")
    name = Column(String(200), nullable=False, comment="商品名称")
    description = Column(Text, nullable=True, comment="商品描述")
    price = Column(Float, nullable=False, comment="售价")
    cost_price = Column(Float, nullable=True, comment="成本价")
    image_url = Column(String(500), nullable=True, comment="商品图片URL")
    category = Column(String(100), nullable=True, comment="商品分类")
    status = Column(Integer, default=1, comment="状态：1-上架，0-下架")
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    # 关联库存表（一对多：一个商品可能有多个SKU，这里简化为一对一，如需多SKU可扩展）
    # 若希望一个商品对应多个SKU，可新建 SKU 表，此处仅作示例
    sku_id = Column(String(50), unique=True, nullable=True, comment="关联的库存SKU ID")
    # 可选：与库存表建立外键关系（但需确保inventory表已存在）
    # __table_args__ = (ForeignKeyConstraint(['sku_id'], ['inventory.sku_id']),)

    __table_args__ = (
        Index("idx_product_status", "status"),
        Index("idx_product_category", "category"),
    )