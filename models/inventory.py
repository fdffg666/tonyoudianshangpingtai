from sqlalchemy import Column, Integer, String, DateTime, Index, UniqueConstraint
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func
import enum

Base = declarative_base()


# 操作类型枚举
class ChangeType(enum.Enum):
    LOCK = "LOCK"  # 锁定库存
    RELEASE = "RELEASE"  # 释放库存
    DEDUCT = "DEDUCT"  # 扣减总库存
    INIT = "INIT"
    RESET = "RESET"  # 初始化后重置库存


# 库存主表
class Inventory(Base):
    __tablename__ = "inventory"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="主键ID")
    sku_id = Column(String(50), nullable=False, comment="商品SKU ID", unique=True)
    total_stock = Column(Integer, default=0, comment="总库存")
    available_stock = Column(Integer, default=0, comment="可用库存")
    locked_stock = Column(Integer, default=0, comment="锁定库存")
    version = Column(Integer, default=0, comment="版本号（乐观锁）")  # 新增：乐观锁字段
    created_at = Column(DateTime, default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), comment="更新时间")

    # 索引（sku_id已唯一，无需重复创建）
    __table_args__ = (
        Index("idx_inventory_updated_at", "updated_at"),  # 可选：按更新时间查询
        {"comment": "库存主表"}
    )


# 库存操作日志表
class InventoryLog(Base):
    __tablename__ = "inventory_log"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="主键ID")
    sku_id = Column(String(50), nullable=False, comment="商品SKU ID")
    order_id = Column(String(50), nullable=False, comment="订单ID")
    biz_id = Column(String(50), nullable=False, comment="业务幂等ID（如ORDER_1001_LOCK）")  # 新增：幂等键
    change_type = Column(String(20), nullable=False, comment="操作类型：LOCK/RELEASE/DEDUCT")
    change_amount = Column(Integer, nullable=False, comment="变更数量")
    before_total = Column(Integer, comment="操作前总库存")
    before_available = Column(Integer, comment="操作前可用库存")
    before_locked = Column(Integer, comment="操作前锁定库存")
    created_at = Column(DateTime, default=func.now(), comment="创建时间")

    # 新增：索引 + 唯一约束（保证biz_id幂等）
    __table_args__ = (
        Index("idx_log_sku_id", "sku_id"),  # 按SKU查询日志
        Index("idx_log_order_id", "order_id"),  # 按订单查询日志
        Index("idx_log_created_at", "created_at"),  # 按时间查询日志
        UniqueConstraint("biz_id", name="uk_log_biz_id"),  # 唯一约束：保证幂等
        {"comment": "库存操作日志表"}
    )