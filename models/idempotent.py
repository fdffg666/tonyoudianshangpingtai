from sqlalchemy import Column, String, Integer, Enum, DateTime, Text
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime
import enum

Base = declarative_base()


# 幂等记录状态枚举
class IdempotentStatus(enum.Enum):
    PROCESSING = "PROCESSING"  # 处理中
    SUCCESS = "SUCCESS"  # 成功
    FAILED = "FAILED"  # 失败


# 专用幂等表（biz_id唯一键）
class IdempotentRecord(Base):
    __tablename__ = "idempotent_record"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="主键ID")
    biz_id = Column(String(64), unique=True, nullable=False, comment="唯一业务ID（如ORDER_1001_LOCK_SKU_001）")
    operation_type = Column(String(32), nullable=False, comment="操作类型：INIT/LOCK/RELEASE/DEDUCT")
    status = Column(Enum(IdempotentStatus), default=IdempotentStatus.PROCESSING, comment="执行状态")
    result = Column(Text, comment="操作结果JSON字符串")
    created_at = Column(DateTime, default=datetime.now, comment="创建时间")
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment="更新时间")

    __table_args__ = {
        "comment": "库存操作幂等记录表（核心：biz_id唯一约束）"
    }