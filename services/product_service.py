# services/product_service.py
from sqlalchemy import select, update, delete, func
from sqlalchemy.exc import SQLAlchemyError
from typing import Optional, List, Dict
from datetime import datetime

from models.product import Product
from services.inventory_service import get_db_session, _ok, _fail, init_sku_stock
from utils.logger import ContextLogger, get_trace_id

logger = ContextLogger(__name__)


def create_product(
    name: str,
    price: float,
    description: Optional[str] = None,
    cost_price: Optional[float] = None,
    image_url: Optional[str] = None,
    category: Optional[str] = None,
    sku_id: Optional[str] = None,
    initial_stock: int = 0
) -> Dict:
    """创建商品，可选同时初始化库存"""
    trace_id = get_trace_id()
    ctx_logger = logger.with_context(trace_id=trace_id, name=name)

    if not name or price <= 0:
        return _fail("商品名称和价格必须提供且价格大于0")

    try:
        with get_db_session() as session:
            # 如果传入了 sku_id，检查是否已存在
            if sku_id:
                existing = session.execute(
                    select(Product).where(Product.sku_id == sku_id)
                ).scalar_one_or_none()
                if existing:
                    return _fail(f"SKU ID {sku_id} 已被使用")

            # 创建商品记录
            product = Product(
                name=name,
                description=description,
                price=price,
                cost_price=cost_price,
                image_url=image_url,
                category=category,
                sku_id=sku_id,
                status=1
            )
            session.add(product)
            session.flush()  # 获取自增ID

            # 如果指定了初始库存，调用库存初始化
            if initial_stock > 0 and sku_id:
                # 注意：init_sku_stock 需要 sku_id 和数量
                inv_result = init_sku_stock(sku_id, initial_stock, force=False)
                if not inv_result["success"]:
                    session.rollback()
                    return _fail(f"库存初始化失败: {inv_result['message']}")

            session.commit()
            ctx_logger.info(f"商品创建成功: id={product.id}, sku={sku_id}")

            return _ok("商品创建成功", {
                "id": product.id,
                "name": product.name,
                "sku_id": product.sku_id,
                "price": product.price,
            })
    except SQLAlchemyError as e:
        ctx_logger.error(f"商品创建失败: {e}", exc_info=True)
        return _fail("数据库错误，请稍后重试")
    except Exception as e:
        ctx_logger.error(f"商品创建异常: {e}", exc_info=True)
        return _fail("系统异常，请稍后重试")


def get_product(product_id: int) -> Dict:
    """查询单个商品详情（含库存信息）"""
    trace_id = get_trace_id()
    ctx_logger = logger.with_context(trace_id=trace_id, product_id=product_id)

    try:
        with get_db_session() as session:
            product = session.execute(
                select(Product).where(Product.id == product_id)
            ).scalar_one_or_none()
            if not product:
                return _fail("商品不存在")

            # 查询关联的库存信息（如果有 sku_id）
            stock_info = None
            if product.sku_id:
                from services.inventory_service import query_inventory
                stock_result = query_inventory(product.sku_id)
                if stock_result["success"]:
                    stock_info = stock_result["data"]

            return _ok("查询成功", {
                "id": product.id,
                "name": product.name,
                "description": product.description,
                "price": product.price,
                "cost_price": product.cost_price,
                "image_url": product.image_url,
                "category": product.category,
                "status": product.status,
                "sku_id": product.sku_id,
                "stock": stock_info,
                "created_at": product.created_at.isoformat() if product.created_at else None,
                "updated_at": product.updated_at.isoformat() if product.updated_at else None,
            })
    except SQLAlchemyError as e:
        ctx_logger.error(f"查询商品失败: {e}", exc_info=True)
        return _fail("数据库错误")


def list_products(
    page: int = 1,
    page_size: int = 20,
    category: Optional[str] = None,
    status: Optional[int] = None,
    keyword: Optional[str] = None
) -> Dict:
    """分页查询商品列表"""
    trace_id = get_trace_id()
    ctx_logger = logger.with_context(trace_id=trace_id)

    try:
        with get_db_session() as session:
            stmt = select(Product)

            if category:
                stmt = stmt.where(Product.category == category)
            if status is not None:
                stmt = stmt.where(Product.status == status)
            if keyword:
                stmt = stmt.where(Product.name.contains(keyword))

            # 总数
            total = session.execute(select(func.count()).select_from(stmt.subquery())).scalar()
            # 分页
            products = session.execute(
                stmt.order_by(Product.created_at.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            ).scalars().all()

            return _ok("查询成功", {
                "list": [
                    {
                        "id": p.id,
                        "name": p.name,
                        "price": p.price,
                        "image_url": p.image_url,
                        "category": p.category,
                        "status": p.status,
                        "sku_id": p.sku_id,
                        "created_at": p.created_at.isoformat() if p.created_at else None,
                    } for p in products
                ],
                "pagination": {
                    "page": page,
                    "page_size": page_size,
                    "total": total,
                    "total_pages": (total + page_size - 1) // page_size if total > 0 else 0
                }
            })
    except SQLAlchemyError as e:
        ctx_logger.error(f"查询商品列表失败: {e}", exc_info=True)
        return _fail("数据库错误")


def update_product(product_id: int, **kwargs) -> Dict:
    """更新商品信息（只更新传入的非空字段）"""
    trace_id = get_trace_id()
    ctx_logger = logger.with_context(trace_id=trace_id, product_id=product_id)

    allowed_fields = {"name", "description", "price", "cost_price", "image_url", "category", "status", "sku_id"}
    update_data = {k: v for k, v in kwargs.items() if k in allowed_fields and v is not None}

    if not update_data:
        return _fail("没有提供可更新的字段")

    try:
        with get_db_session() as session:
            # 检查商品是否存在
            product = session.execute(
                select(Product).where(Product.id == product_id)
            ).scalar_one_or_none()
            if not product:
                return _fail("商品不存在")

            # 如果更新 sku_id，检查是否已被占用
            if "sku_id" in update_data and update_data["sku_id"] != product.sku_id:
                existing = session.execute(
                    select(Product).where(Product.sku_id == update_data["sku_id"])
                ).scalar_one_or_none()
                if existing:
                    return _fail(f"SKU ID {update_data['sku_id']} 已被其他商品使用")

            # 执行更新
            for key, value in update_data.items():
                setattr(product, key, value)
            product.updated_at = datetime.now()
            session.commit()

            ctx_logger.info(f"商品更新成功: id={product_id}, fields={list(update_data.keys())}")
            return _ok("更新成功")
    except SQLAlchemyError as e:
        ctx_logger.error(f"更新商品失败: {e}", exc_info=True)
        return _fail("数据库错误")


def delete_product(product_id: int) -> Dict:
    """删除商品（软删除：将状态置为0，或硬删除，这里使用硬删除）"""
    trace_id = get_trace_id()
    ctx_logger = logger.with_context(trace_id=trace_id, product_id=product_id)

    try:
        with get_db_session() as session:
            result = session.execute(
                delete(Product).where(Product.id == product_id)
            )
            session.commit()
            if result.rowcount == 0:
                return _fail("商品不存在")
            ctx_logger.info(f"商品删除成功: id={product_id}")
            return _ok("删除成功")
    except SQLAlchemyError as e:
        ctx_logger.error(f"删除商品失败: {e}", exc_info=True)
        return _fail("数据库错误")