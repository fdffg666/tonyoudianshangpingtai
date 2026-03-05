# models/payment.py
from sqlalchemy import Column, Integer, String, DECIMAL, DateTime, JSON, ForeignKey, Index
from sqlalchemy.orm import relationship
from datetime import datetime
from models.base import Base  # 统一Base


class PaymentRecord(Base):
    """支付记录表"""
    __tablename__ = 'payment_records'

    id = Column(Integer, primary_key=True, autoincrement=True)
    order_id = Column(Integer, ForeignKey('orders.id', ondelete='RESTRICT'), nullable=False)
    transaction_id = Column(String(64), unique=True, nullable=True, comment='微信支付订单号')
    out_trade_no = Column(String(64), unique=True, nullable=False, comment='商户订单号')
    trade_type = Column(String(16), default='NATIVE', comment='交易类型')
    trade_state = Column(String(32), nullable=True, comment='交易状态')
    pay_amount = Column(DECIMAL(10, 2), nullable=False, comment='支付金额')
    currency = Column(String(8), default='CNY', comment='货币类型')
    payer_openid = Column(String(128), nullable=True, comment='支付用户OpenID')
    code_url = Column(String(512), nullable=True, comment='二维码链接')
    prepay_id = Column(String(128), nullable=True, comment='预支付ID')
    bank_type = Column(String(32), nullable=True, comment='付款银行')
    attach = Column(String(512), nullable=True, comment='附加数据')
    time_start = Column(DateTime, nullable=True, comment='订单创建时间')
    time_expire = Column(DateTime, nullable=True, comment='订单失效时间')
    time_paid = Column(DateTime, nullable=True, comment='支付完成时间')
    notify_data = Column(JSON, nullable=True, comment='回调通知原始数据')
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    # 关联订单
    order = relationship("Order")

    __table_args__ = (
        Index('idx_order_id', 'order_id'),
        Index('idx_trade_state', 'trade_state'),
        Index('idx_time_paid', 'time_paid'),
    )