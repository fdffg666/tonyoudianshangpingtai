# services/cart_service.py
from sqlalchemy import select, delete
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from typing import Dict, List, Optional
from datetime import datetime

from models.cart import Cart, CartItem
from models.product import Product
from services.inventory_service import get_db_session, _ok, _fail
from utils.logger import ContextLogger, get_trace_id

logger = ContextLogger(__name__)


def _get_or_create_cart(session, user_id: int) -> Cart:
    """获取用户的购物车，若不存在则创建（辅助函数）"""
    cart = session.execute(select(Cart).where(Cart.user_id == user_id)).scalar_one_or_none()
    if not cart:
        cart = Cart(user_id=user_id)
        session.add(cart)
        session.flush()  # 获取 cart.id
    return cart


def add_to_cart(user_id: int, product_id: int, quantity: int = 1) -> Dict:
    """
    添加商品到购物车
    - 如果购物车中已存在该商品，则增加数量
    - 如果商品不存在或已下架，返回错误
    """
    trace_id = get_trace_id()
    ctx_logger = logger.with_context(trace_id=trace_id, user_id=user_id, product_id=product_id)

    if quantity <= 0:
        return _fail("数量必须大于0")

    try:
        with get_db_session() as session:
            # 1. 校验商品是否存在且上架
            product = session.execute(
                select(Product).where(Product.id == product_id, Product.status == 1)
            ).scalar_one_or_none()
            if not product:
                return _fail("商品不存在或已下架")

            # 2. 获取或创建购物车
            cart = _get_or_create_cart(session, user_id)

            # 3. 查找是否已存在该商品
            item = session.execute(
                select(CartItem).where(CartItem.cart_id == cart.id, CartItem.product_id == product_id)
            ).scalar_one_or_none()

            if item:
                # 已存在，增加数量
                item.quantity += quantity
                ctx_logger.info(f"更新购物车商品数量: cart_item_id={item.id}, new_quantity={item.quantity}")
            else:
                # 新增
                item = CartItem(cart_id=cart.id, product_id=product_id, quantity=quantity)
                session.add(item)
                ctx_logger.info(f"添加商品到购物车: product_id={product_id}, quantity={quantity}")

            session.commit()
            return _ok("添加成功")
    except IntegrityError as e:
        ctx_logger.error(f"添加购物车数据库完整性错误: {e}", exc_info=True)
        return _fail("添加失败，可能商品或购物车不存在")
    except SQLAlchemyError as e:
        ctx_logger.error(f"添加购物车数据库错误: {e}", exc_info=True)
        return _fail("数据库错误，请稍后重试")
    except Exception as e:
        ctx_logger.error(f"添加购物车未知异常: {e}", exc_info=True)
        return _fail("系统异常，请稍后重试")


def get_cart(user_id: int) -> Dict:
    """
    查询用户的购物车，返回商品详情（包含最新价格、库存状态）
    """
    trace_id = get_trace_id()
    ctx_logger = logger.with_context(trace_id=trace_id, user_id=user_id)

    try:
        with get_db_session() as session:
            cart = session.execute(select(Cart).where(Cart.user_id == user_id)).scalar_one_or_none()
            if not cart:
                return _ok("购物车为空", {"items": [], "total_price": 0.0})

            # 联查商品信息和库存（可选）
            items = session.execute(
                select(CartItem, Product)
                .join(Product, CartItem.product_id == Product.id)
                .where(CartItem.cart_id == cart.id)
            ).all()

            item_list = []
            total = 0.0
            for cart_item, product in items:
                # 可获取库存状态（调用库存服务，可选）
                # from services.inventory_service import query_inventory
                # stock_info = query_inventory(product.sku_id) if product.sku_id else None
                subtotal = product.price * cart_item.quantity
                total += subtotal
                item_list.append({
                    "item_id": cart_item.id,
                    "product_id": product.id,
                    "name": product.name,
                    "price": product.price,
                    "quantity": cart_item.quantity,
                    "subtotal": subtotal,
                    "image_url": product.image_url,
                    "sku_id": product.sku_id,
                    # "stock": stock_info.get("data") if stock_info else None,
                })

            return _ok("查询成功", {
                "cart_id": cart.id,
                "items": item_list,
                "total_price": total
            })
    except SQLAlchemyError as e:
        ctx_logger.error(f"查询购物车数据库错误: {e}", exc_info=True)
        return _fail("数据库错误")
    except Exception as e:
        ctx_logger.error(f"查询购物车未知异常: {e}", exc_info=True)
        return _fail("系统异常")


def update_cart_item(user_id: int, item_id: int, quantity: int) -> Dict:
    """
    更新购物车中某商品的数量
    - 若 quantity <= 0，则删除该商品
    """
    trace_id = get_trace_id()
    ctx_logger = logger.with_context(trace_id=trace_id, user_id=user_id, item_id=item_id, quantity=quantity)

    try:
        with get_db_session() as session:
            # 先验证该商品属于当前用户的购物车
            item = session.execute(
                select(CartItem)
                .join(Cart, CartItem.cart_id == Cart.id)
                .where(Cart.user_id == user_id, CartItem.id == item_id)
            ).scalar_one_or_none()

            if not item:
                return _fail("购物车商品不存在或无权限")

            if quantity <= 0:
                session.delete(item)
                ctx_logger.info(f"删除购物车商品: item_id={item_id}")
            else:
                item.quantity = quantity
                ctx_logger.info(f"更新购物车商品数量: item_id={item_id}, quantity={quantity}")

            session.commit()
            return _ok("更新成功")
    except SQLAlchemyError as e:
        ctx_logger.error(f"更新购物车数据库错误: {e}", exc_info=True)
        return _fail("数据库错误")
    except Exception as e:
        ctx_logger.error(f"更新购物车未知异常: {e}", exc_info=True)
        return _fail("系统异常")


def remove_from_cart(user_id: int, item_id: int) -> Dict:
    """删除购物车中的单个商品"""
    trace_id = get_trace_id()
    ctx_logger = logger.with_context(trace_id=trace_id, user_id=user_id, item_id=item_id)

    try:
        with get_db_session() as session:
            item = session.execute(
                select(CartItem)
                .join(Cart, CartItem.cart_id == Cart.id)
                .where(Cart.user_id == user_id, CartItem.id == item_id)
            ).scalar_one_or_none()

            if not item:
                return _fail("购物车商品不存在或无权限")

            session.delete(item)
            session.commit()
            ctx_logger.info(f"删除购物车商品: item_id={item_id}")
            return _ok("删除成功")
    except SQLAlchemyError as e:
        ctx_logger.error(f"删除购物车数据库错误: {e}", exc_info=True)
        return _fail("数据库错误")
    except Exception as e:
        ctx_logger.error(f"删除购物车未知异常: {e}", exc_info=True)
        return _fail("系统异常")


def clear_cart(user_id: int) -> Dict:
    """清空用户的整个购物车"""
    trace_id = get_trace_id()
    ctx_logger = logger.with_context(trace_id=trace_id, user_id=user_id)

    try:
        with get_db_session() as session:
            cart = session.execute(select(Cart).where(Cart.user_id == user_id)).scalar_one_or_none()
            if cart:
                session.execute(delete(CartItem).where(CartItem.cart_id == cart.id))
                ctx_logger.info(f"清空购物车: cart_id={cart.id}")

            session.commit()
            return _ok("清空成功")
    except SQLAlchemyError as e:
        ctx_logger.error(f"清空购物车数据库错误: {e}", exc_info=True)
        return _fail("数据库错误")
    except Exception as e:
        ctx_logger.error(f"清空购物车未知异常: {e}", exc_info=True)
        return _fail("系统异常")