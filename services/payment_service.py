# services/payment_service.py
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple
from decimal import Decimal

from wechatpayv3 import WeChatPay, WeChatPayType

from models.payment import PaymentRecord
from models.order import Order, OrderStatus
from services.inventory_service import get_db_session, _ok, _fail
from utils.logger import ContextLogger, get_trace_id
from utils.config import (
    WECHATPAY_MCHID, WECHATPAY_APPID, WECHATPAY_APIV3_KEY,
    WECHATPAY_CERT_SERIAL_NO, WECHATPAY_PRIVATE_KEY_PATH,
    WECHATPAY_NOTIFY_URL, WECHATPAY_CERT_DIR, WECHATPAY_PARTNER_MODE
)

logger = ContextLogger(__name__)

_wechatpay_client = None


def get_wechatpay_client() -> Optional[WeChatPay]:
    global _wechatpay_client
    if _wechatpay_client is not None:
        return _wechatpay_client

    if not all([WECHATPAY_MCHID, WECHATPAY_APPID, WECHATPAY_APIV3_KEY,
                WECHATPAY_CERT_SERIAL_NO]):
        logger.error("微信支付配置不完整，请检查环境变量")
        return None

    try:
        with open(WECHATPAY_PRIVATE_KEY_PATH, 'r') as f:
            private_key = f.read()
    except Exception as e:
        logger.error(f"读取商户私钥文件失败: {e}")
        return None

    _wechatpay_client = WeChatPay(
        wechatpay_type=WeChatPayType.NATIVE,
        mchid=WECHATPAY_MCHID,
        private_key=private_key,
        cert_serial_no=WECHATPAY_CERT_SERIAL_NO,
        apiv3_key=WECHATPAY_APIV3_KEY,
        appid=WECHATPAY_APPID,
        notify_url=WECHATPAY_NOTIFY_URL,
        cert_dir=WECHATPAY_CERT_DIR,
        logger=logging.getLogger("wechatpay"),
        partner_mode=WECHATPAY_PARTNER_MODE,
        timeout=(10, 30)
    )
    return _wechatpay_client


def create_native_payment(order_id: int, user_id: int) -> Dict:
    trace_id = get_trace_id()
    ctx_logger = logger.with_context(trace_id=trace_id, order_id=order_id, user_id=user_id)

    try:
        with get_db_session() as session:
            order = session.get(Order, order_id)
            if not order:
                return _fail("订单不存在")
            if order.user_id != user_id:
                return _fail("无权操作该订单")
            if order.status != OrderStatus.PENDING.value:
                return _fail(f"订单当前状态为 {order.status}，不能发起支付")

            # 客服微信号
            customer_service_wechat = "CustomerService123"
            
            # 模拟支付链接，实际返回客服微信号
            code_url = f"wechat://addfriend/{customer_service_wechat}"
            time_expire = datetime.now() + timedelta(hours=24)  # 24小时有效期

            existing_payment = session.query(PaymentRecord).filter(
                PaymentRecord.out_trade_no == order.order_no
            ).first()

            if existing_payment:
                payment = existing_payment
            else:
                payment = PaymentRecord(
                    order_id=order.id,
                    out_trade_no=order.order_no,
                    pay_amount=order.total_amount
                )
                session.add(payment)

            payment.code_url = code_url
            payment.trade_state = 'NOTPAY'
            payment.time_start = datetime.now()
            payment.time_expire = time_expire
            session.commit()

            return _ok("创建支付订单成功", {
                "code_url": code_url,
                "out_trade_no": order.order_no,
                "expire_at": time_expire.isoformat(),
                "customer_service_wechat": customer_service_wechat,
                "message": "请添加客服微信进行支付"
            })

    except Exception as e:
        ctx_logger.error(f"创建支付订单异常: {e}", exc_info=True)
        return _fail("支付系统异常，请稍后重试")


def handle_payment_notify(headers: dict, body: bytes) -> Tuple[bool, str, Optional[Dict]]:
    trace_id = get_trace_id()
    ctx_logger = logger.with_context(trace_id=trace_id)

    # 由于使用客服微信号支付，不需要处理微信支付回调
    # 直接返回成功
    ctx_logger.info("收到支付回调，使用客服微信号支付方式，直接返回成功")
    return True, 'SUCCESS', {"message": "使用客服微信号支付"}


def query_payment(order_id: int, user_id: int) -> Dict:
    trace_id = get_trace_id()
    ctx_logger = logger.with_context(trace_id=trace_id, order_id=order_id, user_id=user_id)

    try:
        with get_db_session() as session:
            order = session.get(Order, order_id)
            if not order:
                return _fail("订单不存在")
            if order.user_id != user_id:
                return _fail("无权查看该订单")

            payment = session.query(PaymentRecord).filter(
                PaymentRecord.out_trade_no == order.order_no
            ).first()
            if not payment:
                return _fail("支付记录不存在")

            # 客服微信号
            customer_service_wechat = "CustomerService123"

            return _ok("查询成功", {
                "out_trade_no": payment.out_trade_no,
                "trade_state": payment.trade_state,
                "pay_amount": float(payment.pay_amount),
                "time_paid": payment.time_paid.isoformat() if payment.time_paid else None,
                "customer_service_wechat": customer_service_wechat,
                "message": "请添加客服微信进行支付"
            })

    except Exception as e:
        ctx_logger.error(f"查询支付异常: {e}", exc_info=True)
        return _fail("查询支付失败，请稍后重试")