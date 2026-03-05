# services/order_service.py
import random
import string
from datetime import datetime
from decimal import Decimal
from typing import List, Dict, Optional
from sqlalchemy import select,func
from sqlalchemy.exc import SQLAlchemyError

from models.order import Order, OrderItem, OrderStatus
from models.product import Product
from services.inventory_service import get_db_session, _ok, _fail
from utils.logger import ContextLogger, get_trace_id

logger = ContextLogger(__name__)


def _generate_order_no() -> str:
    """生成唯一订单号：时间戳 + 随机6位数字 + 校验位（简单实现）"""
    import time
    timestamp = str(int(time.time() * 1000))[-12:]  # 取后12位
    rand = ''.join(random.choices(string.digits, k=6))
    return f"ORD{timestamp}{rand}"

# 创建采购订单
def create_order(
    user_id: int,
    items: List[Dict],
    expected_delivery_date: Optional[str] = None,
    remark: Optional[str] = None
) -> Dict:
    """
    创建采购订单
    :param user_id: 当前用户ID
    :param items: [{"product_id": 1, "quantity": 2}, ...]
    :param expected_delivery_date: 期望交货日期（YYYY-MM-DD）
    :param remark: 备注
    :return: 订单详情
    """
    trace_id = get_trace_id()
    ctx_logger = logger.with_context(trace_id=trace_id, user_id=user_id)

    # 1. 参数校验
    if not items:
        return _fail("订单商品列表不能为空")

    # 2. 校验商品是否存在并获取最新价格
    try:
        with get_db_session() as session:
            product_ids = [item["product_id"] for item in items]
            products = session.execute(
                select(Product).where(Product.id.in_(product_ids), Product.status == 1)
            ).scalars().all()

            if len(products) != len(product_ids):
                # 找出不存在的商品ID
                existing_ids = {p.id for p in products}
                missing = [pid for pid in product_ids if pid not in existing_ids]
                ctx_logger.warning(f"部分商品不存在或已下架: {missing}")
                return _fail(f"商品ID {missing} 不存在或已下架")

            # 构建商品价格映射
            price_map = {p.id: p.price for p in products}

            # 3. 计算总金额并构造订单明细
            total_amount = Decimal('0.00')
            order_items = []
            for item in items:
                pid = item["product_id"]
                qty = item["quantity"]
                if qty <= 0:
                    return _fail(f"商品ID {pid} 数量必须大于0")
                price = Decimal(str(price_map[pid]))
                subtotal = price * qty
                print(
                    f"type(price): {type(price)}, type(subtotal): {type(subtotal)}, type(total_amount): {type(total_amount)}")
                total_amount += subtotal
                order_items.append({
                    "product_id": pid,
                    "quantity": qty,
                    "price": price,
                    "subtotal": subtotal
                })

            # 4. 生成订单号
            order_no = _generate_order_no()

            # 5. 创建订单对象
            order = Order(
                order_no=order_no,
                user_id=user_id,
                total_amount=total_amount,
                expected_delivery_date=datetime.strptime(expected_delivery_date, "%Y-%m-%d").date() if expected_delivery_date else None,
                remark=remark,
                status=OrderStatus.PENDING
            )
            session.add(order)
            session.flush()  # 获取 order.id

            # 6. 添加订单明细
            for oi in order_items:
                item = OrderItem(
                    order_id=order.id,
                    product_id=oi["product_id"],
                    quantity=oi["quantity"],
                    price=oi["price"],
                    subtotal=oi["subtotal"]
                )
                session.add(item)

            session.commit()
            ctx_logger.info(f"订单创建成功: order_id={order.id}, order_no={order_no}")

            # 7. 返回订单信息
            return _ok("订单创建成功", {
                "order_id": order.id,
                "order_no": order.order_no,
                "total_amount": float(total_amount),
                "status": order.status,
                "items": [
                    {
                        "product_id": oi["product_id"],
                        "quantity": oi["quantity"],
                        "price": float(oi["price"]),
                        "subtotal": float(oi["subtotal"])
                    } for oi in order_items
                ],
                "expected_delivery_date": expected_delivery_date,
                "remark": remark,
                "created_at": order.created_at.isoformat()
            })

    except SQLAlchemyError as e:
        ctx_logger.error(f"创建订单数据库错误: {e}", exc_info=True)
        return _fail("数据库错误，请稍后重试")
    except ValueError as e:
        ctx_logger.error(f"日期格式错误: {e}")
        return _fail("期望交货日期格式错误，应为 YYYY-MM-DD")
    except Exception as e:
        ctx_logger.error(f"创建订单未知异常: {e}", exc_info=True)
        return _fail("系统异常，请稍后重试")
from sqlalchemy import func, select
# 查询订单列表（分页、状态筛选）
def list_orders(
    user_id: Optional[int] = None,
    status: Optional[str] = None,
    page: int = 1,
    page_size: int = 20
) -> Dict:
    """
    查询订单列表（分页、状态筛选）
    - 如果 user_id 为 None，则返回所有订单（管理员用）
    - 否则只返回该用户的订单
    """
    trace_id = get_trace_id()
    ctx_logger = logger.with_context(trace_id=trace_id)

    try:
        with get_db_session() as session:
            stmt = select(Order)
            if user_id is not None:
                stmt = stmt.where(Order.user_id == user_id)
            if status:
                # 校验状态合法性
                try:
                    OrderStatus(status)
                except ValueError:
                    return _fail(f"无效的订单状态: {status}")
                stmt = stmt.where(Order.status == status)

            total = session.execute(select(func.count()).select_from(stmt.subquery())).scalar()
            orders = session.execute(
                stmt.order_by(Order.created_at.desc())
                .offset((page-1)*page_size)
                .limit(page_size)
            ).scalars().all()

            return _ok("查询成功", {
                "list": [
                    {
                        "id": o.id,
                        "order_no": o.order_no,
                        "total_amount": float(o.total_amount),
                        "status": o.status,
                        "created_at": o.created_at.isoformat(),
                        "item_count": len(o.items)  # 需要提前加载 items？这里会触发 lazy load，可优化
                    } for o in orders
                ],
                "pagination": {
                    "page": page,
                    "page_size": page_size,
                    "total": total,
                    "total_pages": (total + page_size - 1) // page_size
                }
            })
    except SQLAlchemyError as e:
        ctx_logger.error(f"查询订单列表失败: {e}", exc_info=True)
        return _fail("数据库错误")
#  查询订单详情（包含订单明细）
def get_order_detail(order_id: int, current_user_id: int, is_admin: bool = False) -> Dict:
    trace_id = get_trace_id()
    ctx_logger = logger.with_context(trace_id=trace_id, order_id=order_id)

    try:
        with get_db_session() as session:
            order = session.get(Order, order_id)
            if not order:
                return _fail("订单不存在")
            if not is_admin and order.user_id != current_user_id:
                return _fail("无权查看该订单")

            items = []
            for item in order.items:
                items.append({
                    "id": item.id,
                    "product_id": item.product_id,
                    "quantity": item.quantity,
                    "price": float(item.price),
                    "subtotal": float(item.subtotal),
                    "product_name": item.product.name if item.product else None,
                })

            return _ok("查询成功", {
                "id": order.id,
                "order_no": order.order_no,
                "total_amount": float(order.total_amount),
                "status": order.status,
                "expected_delivery_date": order.expected_delivery_date.isoformat() if order.expected_delivery_date else None,
                "remark": order.remark,
                "created_at": order.created_at.isoformat(),
                "items": items
            })
    except SQLAlchemyError as e:
        ctx_logger.error(f"查询订单详情失败: {e}", exc_info=True)
        return _fail("数据库错误")

# 用户取消订单（仅限待处理状态）
def cancel_order(order_id: int, user_id: int) -> Dict:
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
                return _fail(f"订单当前状态为 {order.status}，不能取消")

            order.status = OrderStatus.CANCELLED.value
            session.commit()
            ctx_logger.info(f"订单已取消: order_id={order_id}")
            return _ok("订单已取消", {"order_id": order.id, "status": order.status})
    except SQLAlchemyError as e:
        ctx_logger.error(f"取消订单失败: {e}", exc_info=True)
        return _fail("数据库错误")

#管理员或相关操作员更新订单状态（如确认、发货、完成等）
def update_order_status(order_id: int, new_status: str, operator_id: int) -> Dict:
    trace_id = get_trace_id()
    ctx_logger = logger.with_context(trace_id=trace_id, order_id=order_id, operator_id=operator_id)

    try:
        status_enum = OrderStatus(new_status)
    except ValueError:
        return _fail(f"无效的订单状态: {new_status}，可选值: {[s.value for s in OrderStatus]}")

    try:
        with get_db_session() as session:
            order = session.get(Order, order_id)
            if not order:
                return _fail("订单不存在")
            old_status = order.status
            if old_status == new_status:
                return _fail("订单状态无变化")
            order.status = new_status
            session.commit()
            ctx_logger.info(f"订单状态已更新: {old_status} -> {new_status}")
            return _ok("状态更新成功", {"order_id": order.id, "status": order.status})
    except SQLAlchemyError as e:
        ctx_logger.error(f"更新订单状态失败: {e}", exc_info=True)
        return _fail("数据库错误")