# api/product_routes.py
from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, Field
from typing import Optional
from api.auth_routes import get_current_user, require_merchant

from services.product_service import (
    create_product,
    get_product,
    list_products,
    update_product,
    delete_product,
)
from api.auth_routes import get_current_user  # 复用认证依赖

router = APIRouter(prefix="/products", tags=["商品管理"])


# ---------- 请求模型 ----------
class ProductCreateRequest(BaseModel):
    name: str = Field(..., max_length=200)
    price: float = Field(..., gt=0)
    description: Optional[str] = None
    cost_price: Optional[float] = Field(None, gt=0)
    image_url: Optional[str] = None
    category: Optional[str] = None
    sku_id: Optional[str] = Field(None, max_length=50)
    initial_stock: int = Field(0, ge=0, description="初始库存，大于0时会自动初始化库存")


class ProductUpdateRequest(BaseModel):
    name: Optional[str] = Field(None, max_length=200)
    price: Optional[float] = Field(None, gt=0)
    description: Optional[str] = None
    cost_price: Optional[float] = Field(None, gt=0)
    image_url: Optional[str] = None
    category: Optional[str] = None
    sku_id: Optional[str] = Field(None, max_length=50)
    status: Optional[int] = Field(None, ge=0, le=1)


# ---------- 路由 ----------
@router.post("")
async def api_create_product(
    req: ProductCreateRequest,
    user=Depends(require_merchant)  # 需要登录
):
    """创建商品（可选同时初始化库存）"""
    result = create_product(
        name=req.name,
        price=req.price,
        description=req.description,
        cost_price=req.cost_price,
        image_url=req.image_url,
        category=req.category,
        sku_id=req.sku_id,
        initial_stock=req.initial_stock,
    )
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
    return result


@router.get("/{product_id}")
async def api_get_product(
    product_id: int,
    user=Depends(require_merchant)
):
    """获取商品详情"""
    result = get_product(product_id)
    if not result["success"]:
        raise HTTPException(status_code=404, detail=result["message"])
    return result


@router.get("")
async def api_list_products(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    category: Optional[str] = None,
    status: Optional[int] = Query(None, ge=0, le=1),
    keyword: Optional[str] = None,
    user=Depends(require_merchant)
):
    """分页查询商品列表"""
    result = list_products(
        page=page,
        page_size=page_size,
        category=category,
        status=status,
        keyword=keyword,
    )
    return result


@router.put("/{product_id}")
async def api_update_product(
    product_id: int,
    req: ProductUpdateRequest,
    user=Depends(require_merchant)
):
    """更新商品信息"""
    # 过滤掉 None 值
    update_data = {k: v for k, v in req.dict().items() if v is not None}
    result = update_product(product_id, **update_data)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
    return result


@router.delete("/{product_id}")
async def api_delete_product(
    product_id: int,
    user=Depends(require_merchant)
):
    """删除商品（硬删除）"""
    result = delete_product(product_id)
    if not result["success"]:
        raise HTTPException(status_code=404, detail=result["message"])
    return result