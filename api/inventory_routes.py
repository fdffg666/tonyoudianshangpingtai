# api/inventory_routes.py
from fastapi import APIRouter, HTTPException, Query, Path, Depends
from pydantic import BaseModel, Field
from typing import Optional, List

from services.inventory_service import (
    init_sku_stock,
    lock_stock,
    release_stock,
    deduct_stock,
    query_inventory,
    query_inventory_log
)
from api.auth_routes import get_current_user, require_merchant  # 导入需要的依赖

router = APIRouter(prefix="/inventory", tags=["库存管理"])

# ---------- 请求/响应模型 ----------
class InitStockRequest(BaseModel):
    sku_id: str = Field(..., description="商品SKU ID")
    total_stock: int = Field(..., gt=0, description="初始化总库存")
    force: bool = Field(False, description="是否强制重置（忽略幂等）")

class LockStockRequest(BaseModel):
    sku_id: str
    lock_num: int = Field(..., gt=0)
    order_id: str
    lock_timeout: int = Field(30, ge=1, description="分布式锁超时时间（秒）")

class ReleaseStockRequest(BaseModel):
    sku_id: str
    lock_num: int = Field(..., gt=0)
    order_id: str
    lock_timeout: int = 30

class DeductStockRequest(BaseModel):
    sku_id: str
    deduct_num: int = Field(..., gt=0)
    order_id: str
    lock_timeout: int = 30

class InventoryResponse(BaseModel):
    success: bool
    message: str
    data: Optional[dict] = None

# ---------- 库存操作接口 ----------
# 初始化库存：仅商家/root可操作
@router.post("/init", response_model=InventoryResponse)
async def api_init_stock(req: InitStockRequest, user=Depends(require_merchant)):
    """初始化或重置SKU库存（需要商家权限）"""
    result = init_sku_stock(req.sku_id, req.total_stock, req.force)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
    return result

# 锁定库存：普通用户可调用（下单时使用）
@router.post("/lock", response_model=InventoryResponse)
async def api_lock_stock(req: LockStockRequest, user=Depends(get_current_user)):
    """锁定库存（普通用户下单时调用）"""
    result = lock_stock(req.sku_id, req.lock_num, req.order_id, req.lock_timeout)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
    return result

# 释放库存：普通用户可调用（取消订单时使用）
@router.post("/release", response_model=InventoryResponse)
async def api_release_stock(req: ReleaseStockRequest, user=Depends(get_current_user)):
    """释放锁定库存（普通用户取消订单时调用）"""
    result = release_stock(req.sku_id, req.lock_num, req.order_id, req.lock_timeout)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
    return result

# 扣减库存：仅商家/root可操作（支付成功后由系统调用）
@router.post("/deduct", response_model=InventoryResponse)
async def api_deduct_stock(req: DeductStockRequest, user=Depends(require_merchant)):
    """扣减总库存（支付成功后调用，需要商家权限）"""
    result = deduct_stock(req.sku_id, req.deduct_num, req.order_id, req.lock_timeout)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
    return result

# 读操作：仅需登录（普通用户可访问）
@router.get("/query/{sku_id}", response_model=InventoryResponse)
async def api_query_inventory(sku_id: str = Path(..., description="SKU ID"), user=Depends(get_current_user)):
    """查询单个SKU库存"""
    result = query_inventory(sku_id)
    if not result["success"]:
        raise HTTPException(status_code=404, detail=result["message"])
    return result

@router.get("/query", response_model=InventoryResponse)
async def api_query_all_inventory(user=Depends(get_current_user)):
    """查询所有SKU库存"""
    result = query_inventory()
    return result

@router.get("/logs", response_model=InventoryResponse)
async def api_query_logs(
    sku_id: Optional[str] = Query(None, description="SKU ID"),
    order_id: Optional[str] = Query(None, description="订单ID"),
    change_type: Optional[str] = Query(None, description="操作类型 LOCK/RELEASE/DEDUCT/INIT"),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    user=Depends(get_current_user)
):
    """查询库存操作日志"""
    result = query_inventory_log(sku_id, order_id, change_type, page, page_size)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
    return result