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

            existing_payment = session.query(PaymentRecord).filter(
                PaymentRecord.out_trade_no == order.order_no
            ).first()

            if existing_payment and existing_payment.code_url and existing_payment.time_expire > datetime.now():
                return _ok("获取支付二维码成功", {
                    "code_url": existing_payment.code_url,
                    "out_trade_no": order.order_no,
                    "expire_at": existing_payment.time_expire.isoformat()
                })

            client = get_wechatpay_client()
            if not client:
                return _fail("微信支付客户端初始化失败，请检查配置")

            time_expire = datetime.now() + timedelta(hours=2)
            code, message = client.pay(
                description=f"订单支付：{order.order_no}",
                out_trade_no=order.order_no,
                amount={'total': int(order.total_amount * 100)},
                time_expire=time_expire.strftime('%Y-%m-%dT%H:%M:%S+08:00'),
                pay_type=WeChatPayType.NATIVE
            )

            ctx_logger.info(f"微信支付下单响应: code={code}, message={message}")

            if code != 200:
                return _fail(f"微信支付下单失败: {message}")

            resp_data = json.loads(message)
            code_url = resp_data.get('code_url')
            prepay_id = resp_data.get('prepay_id')

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
            payment.prepay_id = prepay_id
            payment.trade_state = 'NOTPAY'
            payment.time_start = datetime.now()
            payment.time_expire = time_expire
            session.commit()

            return _ok("创建支付订单成功", {
                "code_url": code_url,
                "out_trade_no": order.order_no,
                "expire_at": time_expire.isoformat()
            })

    except Exception as e:
        ctx_logger.error(f"创建支付订单异常: {e}", exc_info=True)
        return _fail("支付系统异常，请稍后重试")


def handle_payment_notify(headers: dict, body: bytes) -> Tuple[bool, str, Optional[Dict]]:
    trace_id = get_trace_id()
    ctx_logger = logger.with_context(trace_id=trace_id)

    client = get_wechatpay_client()
    if not client:
        ctx_logger.error("微信支付客户端未初始化")
        return False, 'FAIL', None

    try:
        result = client.callback(headers, body)
        if not result:
            ctx_logger.warning("回调验证失败")
            return False, 'FAIL', None

        ctx_logger.info(f"支付回调解密结果: {result}")

        out_trade_no = result.get('out_trade_no')
        transaction_id = result.get('transaction_id')
        trade_state = result.get('trade_state', 'SUCCESS')
        payer_openid = result.get('payer', {}).get('openid')
        bank_type = result.get('bank_type')
        time_paid_str = result.get('success_time')

        if not out_trade_no:
            ctx_logger.error("回调数据缺少out_trade_no")
            return False, 'FAIL', None

        with get_db_session() as session:
            payment = session.query(PaymentRecord).filter(
                PaymentRecord.out_trade_no == out_trade_no
            ).first()
            if not payment:
                ctx_logger.error(f"支付记录不存在: {out_trade_no}")
                return False, 'FAIL', None

            payment.transaction_id = transaction_id
            payment.trade_state = trade_state
            payment.payer_openid = payer_openid
            payment.bank_type = bank_type
            payment.notify_data = result
            if time_paid_str:
                try:
                    payment.time_paid = datetime.fromisoformat(time_paid_str.replace('Z', '+00:00'))
                except:
                    payment.time_paid = datetime.now()

            if trade_state == 'SUCCESS':
                order = session.get(Order, payment.order_id)
                if order and order.status == OrderStatus.PENDING.value:
                    order.status = OrderStatus.PAID.value
                    ctx_logger.info(f"订单支付成功: order_id={order.id}")

            session.commit()

        return True, 'SUCCESS', result

    except Exception as e:
        ctx_logger.error(f"处理支付回调异常: {e}", exc_info=True)
        return False, 'FAIL', None


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

            if payment.trade_state in ['SUCCESS', 'CLOSED', 'REFUND']:
                return _ok("查询成功", {
                    "out_trade_no": payment.out_trade_no,
                    "trade_state": payment.trade_state,
                    "transaction_id": payment.transaction_id,
                    "pay_amount": float(payment.pay_amount),
                    "time_paid": payment.time_paid.isoformat() if payment.time_paid else None
                })

            client = get_wechatpay_client()
            if not client:
                return _fail("微信支付客户端初始化失败")

            code, message = client.query(order.order_no)
            if code != 200:
                ctx_logger.warning(f"查单失败: code={code}, message={message}")
                return _ok("查询成功（本地缓存）", {
                    "out_trade_no": payment.out_trade_no,
                    "trade_state": payment.trade_state,
                    "transaction_id": payment.transaction_id,
                    "pay_amount": float(payment.pay_amount),
                    "time_paid": payment.time_paid.isoformat() if payment.time_paid else None
                })

            query_data = json.loads(message)
            trade_state = query_data.get('trade_state')
            transaction_id = query_data.get('transaction_id')
            time_paid_str = query_data.get('success_time')

            payment.trade_state = trade_state
            if transaction_id:
                payment.transaction_id = transaction_id
            if time_paid_str:
                try:
                    payment.time_paid = datetime.fromisoformat(time_paid_str.replace('Z', '+00:00'))
                except:
                    payment.time_paid = datetime.now()

            if trade_state == 'SUCCESS':
                if order.status == OrderStatus.PENDING.value:
                    order.status = OrderStatus.PAID.value

            session.commit()

            return _ok("查询成功", {
                "out_trade_no": order.order_no,
                "trade_state": trade_state,
                "transaction_id": transaction_id,
                "pay_amount": float(payment.pay_amount),
                "time_paid": payment.time_paid.isoformat() if payment.time_paid else None
            })

    except Exception as e:
        ctx_logger.error(f"查询支付异常: {e}", exc_info=True)
        return _fail("查询支付失败，请稍后重试")