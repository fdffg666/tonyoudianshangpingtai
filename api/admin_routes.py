# api/admin_routes.py
from fastapi import APIRouter, HTTPException, Depends,Request, Form
from pydantic import BaseModel
from typing import Optional, List
from fastapi.templating import Jinja2Templates
from sqlalchemy import select, update
from services.order_service import confirm_order_payment
from models.user import User
from services.inventory_service import get_db_session, _ok, _fail
from api.auth_routes import require_root, get_current_user_obj,require_merchant
from services.auth_service import _generate_jwt_token, verify_token

router = APIRouter(prefix="/admin", tags=["管理员管理"])
templates = Jinja2Templates(directory="templates")


# ---------- 请求模型 ----------
class CreateMerchantRequest(BaseModel):
    phone_number: str
    password: str
    nickname: Optional[str] = None
class ConfirmPaymentRequest(BaseModel):
    order_id: int

class UpdateMerchantStatusRequest(BaseModel):
    status: int  # 0-禁用，1-正常


# ---------- 路由 ----------
@router.post("/merchants")
async def create_merchant(
        req: CreateMerchantRequest,
        admin: User = Depends(require_root)  # 只有 root 可调用
):
    """创建商家管理员账号（由 root 操作）"""
    from services.auth_service import register_by_password
    # 复用注册逻辑，但强制设置 role='merchant'
    result = register_by_password(req.phone_number, req.password, req.nickname)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])

    # 修改角色为 merchant
    user_id = result["data"]["user_id"]
    with get_db_session() as session:
        session.execute(
            update(User)
            .where(User.id == user_id)
            .values(role='merchant')
        )
        session.commit()

    return {"success": True, "message": "商家创建成功", "data": {"user_id": user_id}}


@router.get("/merchants")
async def list_merchants(admin: User = Depends(require_root)):
    """获取所有商家管理员列表"""
    with get_db_session() as session:
        merchants = session.execute(
            select(User).where(User.role == 'merchant')
        ).scalars().all()
        for m in merchants:
            print("ORM mapped columns:", m.__table__.columns.keys())
            break
    return _ok(data=[
            {
                "id": m.id,
                "phone": m.phone_number,
                "nickname": m.nickname,
                "status": m.status,
                "created_at": m.created_at.isoformat() if m.created_at else None,
            } for m in merchants
        ])


@router.put("/merchants/{user_id}/status")
async def update_merchant_status(
        user_id: int,
        req: UpdateMerchantStatusRequest,
        admin: User = Depends(require_root)
):
    """启用或禁用商家账号"""
    with get_db_session() as session:
        user = session.execute(
            select(User).where(User.id == user_id, User.role == 'merchant')
        ).scalar_one_or_none()
        if not user:
            raise HTTPException(status_code=404, detail="商家不存在")
        user.status = req.status
        session.commit()
    return _ok("状态更新成功")
@router.post("/orders/confirm-payment")
async def api_confirm_payment(
    req: ConfirmPaymentRequest,
    admin: User = Depends(require_merchant)  # 商家或root可操作
):
    """客服确认订单已付款"""
    result = confirm_order_payment(req.order_id, admin.id)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
    return result
@router.get("/orders/pending", name="admin_pending_orders")
async def admin_pending_orders(
    request: Request,
    admin: User = Depends(require_merchant)  # 需要商家权限
):
    """显示待确认订单列表"""
    with get_db_session() as session:
        orders = session.execute(
            select(Order).where(Order.status == OrderStatus.PENDING.value)
        ).scalars().all()
    return templates.TemplateResponse(
        "admin/orders.html",
        {"request": request, "orders": orders}
    )

@router.post("/orders/{order_id}/confirm")
async def admin_confirm_order(
    order_id: int,
    admin: User = Depends(require_merchant),
    request: Request = None  # 可选，用于重定向
):
    """处理确认付款表单提交"""
    result = confirm_order_payment(order_id, admin.id)
    if result["success"]:
        # 成功后重定向回待确认列表
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url="/admin/orders/pending", status_code=303)
    else:
        # 失败可返回错误页面，这里简单返回 JSON
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=400, content={"message": result["message"]})