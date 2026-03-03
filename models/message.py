# models/message.py
from sqlalchemy import Column, String, Integer, DateTime, Enum
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime
import enum

Base = declarative_base()

# 消息状态枚举
class MessageStatus(enum.Enum):
    PENDING = "PENDING"   # 待发送
    SENT = "SENT"         # 发送成功
    FAILED = "FAILED"     # 发送失败（达到重试上限）
    RETRYING = "RETRYING" # 重试中

class Message(Base):
    __tablename__ = "message"
    id = Column(Integer, primary_key=True, autoincrement=True)
    biz_id = Column(String, nullable=False, comment="业务ID")
    topic = Column(String, nullable=False, comment="MQ主题")
    message = Column(String, nullable=False, comment="消息内容（JSON字符串）")
    status = Column(Enum(MessageStatus), default=MessageStatus.PENDING, comment="消息状态")
    retry_times = Column(Integer, default=0, comment="已重试次数")
    max_retry = Column(Integer, default=3, comment="最大重试次数")
    next_retry_time = Column(DateTime, default=datetime.now, comment="下次重试时间（退避策略）")
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)