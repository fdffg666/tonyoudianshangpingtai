# api/payment_routes.py
from fastapi import APIRouter, HTTPException, Depends, Request, Header
from pydantic import BaseModel, Field
from typing import Optional,Tuple, Dict

from services.payment_service import (
    create_native_payment,
    handle_payment_notify,
    query_payment
)
from api.auth_routes import get_current_user
from utils.logger import ContextLogger, get_trace_id

router = APIRouter(prefix="/payments", tags=["支付"])
logger = ContextLogger(__name__)


# ---------- 请求/响应模型 ----------
class PaymentCreateRequest(BaseModel):
    order_id: int = Field(..., description="订单ID")


class PaymentCreateResponse(BaseModel):
    code_url: str
    out_trade_no: str
    expire_at: str


# ---------- 接口 ----------
@router.post("/native")
async def api_create_native_payment(
        req: PaymentCreateRequest,
        user: dict = Depends(get_current_user)
):
    """
    创建Native支付订单，返回二维码链接
    前端拿到code_url后生成二维码供用户扫码
    """
    result = create_native_payment(req.order_id, user["user_id"])
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
    return result

def handle_payment_notify(headers: dict, body: bytes) -> Tuple[bool, str, Optional[Dict]]:
    client = get_wechatpay_client()
    if not client:
        return False, 'FAIL', None
    try:
        # 关键：client.callback 会验证签名并解密
        result = client.callback(headers, body)
        if not result:
            return False, 'FAIL', None
        # ... 处理支付成功逻辑 ...
        return True, 'SUCCESS', result
    except Exception as e:
        logger.error(f"回调处理异常: {e}")
        return False, 'FAIL', None

@router.post("/notify")
async def api_payment_notify(
        request: Request,
        # 微信回调会携带这些头信息用于签名验证
        wechatpay_signature: Optional[str] = Header(None, alias="Wechatpay-Signature"),
        wechatpay_serial: Optional[str] = Header(None, alias="Wechatpay-Serial"),
        wechatpay_nonce: Optional[str] = Header(None, alias="Wechatpay-Nonce"),
        wechatpay_timestamp: Optional[str] = Header(None, alias="Wechatpay-Timestamp"),
):
    """
    微信支付结果回调接口（需公网可访问）
    微信服务器会POST请求此接口，携带支付结果[citation:6]
    """
    trace_id = get_trace_id()
    ctx_logger = logger.with_context(trace_id=trace_id)

    # 获取请求头（用于签名验证）
    headers = {
        "Wechatpay-Signature": wechatpay_signature,
        "Wechatpay-Serial": wechatpay_serial,
        "Wechatpay-Nonce": wechatpay_nonce,
        "Wechatpay-Timestamp": wechatpay_timestamp,
    }

    # 读取请求体
    body = await request.body()

    ctx_logger.info(f"收到支付回调: headers={headers}, body={body.decode('utf-8', errors='ignore')}")

    # 处理回调
    success, response_msg, data = handle_payment_notify(dict(headers), body)

    if success:
        ctx_logger.info(f"回调处理成功: {data}")
        return response_msg  # 返回 'SUCCESS' 给微信服务器
    else:
        ctx_logger.warning(f"回调处理失败")
        return response_msg  # 返回 'FAIL' 给微信服务器


@router.get("/{order_id}")
async def api_query_payment(
        order_id: int,
        user: dict = Depends(get_current_user)
):
    """
    查询订单支付结果
    """
    result = query_payment(order_id, user["user_id"])
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
    return result