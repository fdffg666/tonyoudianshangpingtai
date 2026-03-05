# api/cart_routes.py
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import Optional

from services.cart_service import (
    add_to_cart,
    get_cart,
    update_cart_item,
    remove_from_cart,
    clear_cart,
)
from api.auth_routes import get_current_user  # 复用已有的用户依赖

router = APIRouter(prefix="/cart", tags=["购物车"])


# ---------- 请求模型 ----------
class AddItemRequest(BaseModel):
    product_id: int = Field(..., description="商品ID")
    quantity: int = Field(1, ge=1, description="数量")


class UpdateItemRequest(BaseModel):
    quantity: int = Field(..., ge=0, description="数量（0表示删除）")


# ---------- 接口 ----------
@router.post("/items")
async def api_add_to_cart(
    req: AddItemRequest,
    user: dict = Depends(get_current_user)  # user 包含 user_id
):
    """添加商品到购物车"""
    user_id = user["user_id"]
    result = add_to_cart(user_id, req.product_id, req.quantity)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
    return result


@router.get("")
async def api_get_cart(user: dict = Depends(get_current_user)):
    """获取当前用户的购物车"""
    user_id = user["user_id"]
    return get_cart(user_id)


@router.put("/items/{item_id}")
async def api_update_cart_item(
    item_id: int,
    req: UpdateItemRequest,
    user: dict = Depends(get_current_user)
):
    """更新购物车商品数量（置0删除）"""
    user_id = user["user_id"]
    result = update_cart_item(user_id, item_id, req.quantity)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
    return result


@router.delete("/items/{item_id}")
async def api_remove_item(
    item_id: int,
    user: dict = Depends(get_current_user)
):
    """从购物车删除指定商品"""
    user_id = user["user_id"]
    result = remove_from_cart(user_id, item_id)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
    return result


@router.delete("")
async def api_clear_cart(user: dict = Depends(get_current_user)):
    """清空购物车"""
    user_id = user["user_id"]
    result = clear_cart(user_id)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
    return result