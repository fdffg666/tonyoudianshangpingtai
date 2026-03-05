# api/order_routes.py
from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, Field, validator
from typing import List, Optional
from datetime import date
import traceback

from services.order_service import create_order,list_orders,get_order_detail,cancel_order,update_order_status
from api.auth_routes import get_current_user,require_merchant  # 复用认证依赖，返回 {"user_id": ...}
from models.user import User
router = APIRouter(prefix="/orders", tags=["订单管理"])


# ---------- 请求模型 ----------
class OrderItemRequest(BaseModel):
    product_id: int = Field(..., description="商品ID")
    quantity: int = Field(..., gt=0, description="订购数量")

    @validator('quantity')
    def quantity_must_be_positive(cls, v):
        if v <= 0:
            raise ValueError('数量必须大于0')
        return v


class CreateOrderRequest(BaseModel):
    items: List[OrderItemRequest] = Field(..., min_items=1, description="商品列表")
    expected_delivery_date: Optional[str] = Field(None, description="期望交货日期，格式 YYYY-MM-DD")
    remark: Optional[str] = Field(None, max_length=500, description="备注")

    @validator('expected_delivery_date')
    def validate_date(cls, v):
        if v:
            try:
                date.fromisoformat(v)
            except ValueError:
                raise ValueError('日期格式错误，应为 YYYY-MM-DD')
        return v

class UpdateOrderStatusRequest(BaseModel):
    status: str = Field(..., description="新状态，可选: pending, confirmed, shipped, completed, cancelled")

# ---------- 接口 ----------
@router.post("")
async def api_create_order(
    req: CreateOrderRequest,
    user: dict = Depends(get_current_user)  # 或 Depends(require_merchant) 强制商家
):
    """
    创建采购订单（需要登录，建议仅商家可操作）
    """
    try:
        user_id = user["user_id"]
        items_dict = [item.dict() for item in req.items]
        result = create_order(
            user_id=user_id,
            items=items_dict,
            expected_delivery_date=req.expected_delivery_date,
            remark=req.remark
        )
        if not result["success"]:
            raise HTTPException(status_code=400, detail=result["message"])
        return result
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"创建订单未知异常: {e}")
        raise HTTPException(status_code=500, detail="系统异常，请稍后重试")

@router.get("")
async def api_list_orders(
    status: Optional[str] = Query(None, description="按状态筛选"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: dict = Depends(get_current_user)
):
    # 暂只返回当前用户的订单，后续可根据角色扩展
    result = list_orders(user_id=user["user_id"], status=status, page=page, page_size=page_size)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
    return result
# 注意：订单详情接口需要区分用户权限，普通用户只能查看自己的订单，商家管理员可以查看所有订单
@router.get("/{order_id}")
async def api_get_order(order_id: int, user: dict = Depends(get_current_user)):
    result = get_order_detail(order_id, user["user_id"], is_admin=False)
    if not result["success"]:
        if "不存在" in result["message"]:
            raise HTTPException(status_code=404, detail=result["message"])
        elif "无权" in result["message"]:
            raise HTTPException(status_code=403, detail=result["message"])
        else:
            raise HTTPException(status_code=400, detail=result["message"])
    return result
# 取消订单接口，普通用户只能取消自己的订单，商家管理员可以取消任何订单
@router.post("/{order_id}/cancel")
async def api_cancel_order(order_id: int, user: dict = Depends(get_current_user)):
    result = cancel_order(order_id, user["user_id"])
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
    return result
# 更新订单状态接口，只有商家管理员可以调用，且只能更新为特定状态（如：待发货、已发货、已完成等）
@router.put("/{order_id}/status")
async def api_update_order_status(
    order_id: int,
    req: UpdateOrderStatusRequest,
    admin: User = Depends(require_merchant)  # 需要导入 require_merchant
):
    result = update_order_status(order_id, req.status, admin.id)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
    return result