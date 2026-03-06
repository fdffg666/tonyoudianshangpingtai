# ========== 1. 基础导入 ==========
import sys
import os
import time
import logging
import threading
import traceback
import json
from datetime import datetime, timedelta
from typing import Dict, Callable, List, Optional
from contextlib import contextmanager

# 规范添加根路径
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# ========== 2. 依赖导入 ==========
from sqlalchemy import create_engine, select, func, case, text
from sqlalchemy.orm import sessionmaker,Session
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from models.base import Base
from utils.db import get_db_session
# Redis 依赖检查
try:
    from redis.exceptions import RedisError
except ImportError:
    class RedisError(Exception):
        pass

# 导入配置和工具（需确保这些模块存在）
from utils.config import (
    DATABASE_URL,
    REDIS_LOCK_EX,
    REDIS_CONFIG,
    CURRENT_ISOLATION_LEVEL,
    MQ_CONFIG
)
from utils.logger import ContextLogger, get_trace_id
from utils.exceptions import BusinessException, SystemException
from utils.redis_lock import redis_lock, redis_client

# 监控和 MQ 模块（允许 Mock）
try:
    from utils.metrics import increment_counter, observe_duration
except ImportError:
    logger = ContextLogger(__name__)
    logger.error("监控模块缺失，启用 Mock")
    def increment_counter(name, tags=None):
        logger.warning(f"[Mock] increment_counter: {name} {tags}")
    def observe_duration(name, tags=None):
        def decorator(func):
            def wrapper(*args, **kwargs):
                logger.warning(f"[Mock] observe_duration: {name} {tags}")
                return func(*args, **kwargs)
            return wrapper
        return decorator

try:
    from utils.mq import send_mq_msg
except ImportError:
    logger = ContextLogger(__name__)
    logger.error("MQ模块缺失，启用 Mock")
    def send_mq_msg(topic: str, msg: dict):
        logger.warning(f"[Mock] 发送消息到 {topic}: {msg}")

# ========== 3. 数据模型（若 models 模块不存在，则在此定义）==========
try:
    from models.inventory import Base, Inventory, InventoryLog, ChangeType
    from models.message import Message, MessageStatus
except ImportError:
    from sqlalchemy.ext.declarative import declarative_base
    from sqlalchemy import Column, String, Integer, DateTime, UniqueConstraint, Enum
    import enum

    Base = declarative_base()

    class MessageStatus(enum.Enum):
        PENDING = "PENDING"
        SENT = "SENT"
        FAILED = "FAILED"
        RETRYING = "RETRYING"

    class ChangeType(enum.Enum):
        INIT = "INIT"
        RESET = "RESET"
        LOCK = "LOCK"
        RELEASE = "RELEASE"
        DEDUCT = "DEDUCT"

    class Inventory(Base):
        __tablename__ = "inventory"
        sku_id = Column(String, primary_key=True)
        total_stock = Column(Integer, default=0, nullable=False)
        available_stock = Column(Integer, default=0, nullable=False)
        locked_stock = Column(Integer, default=0, nullable=False)
        version = Column(Integer, default=1, nullable=False)
        created_at = Column(DateTime, default=datetime.now)
        updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    class InventoryLog(Base):
        __tablename__ = "inventory_log"
        id = Column(Integer, primary_key=True, autoincrement=True)
        sku_id = Column(String, nullable=False)
        order_id = Column(String, nullable=False)
        biz_id = Column(String, nullable=False)
        change_type = Column(String, nullable=False)
        change_amount = Column(Integer, nullable=False)
        before_total = Column(Integer, default=0)
        before_available = Column(Integer, default=0)
        before_locked = Column(Integer, default=0)
        created_at = Column(DateTime, default=datetime.now)
        __table_args__ = (UniqueConstraint("biz_id", name="uk_biz_id"),)

    class Message(Base):
        __tablename__ = "message"
        id = Column(Integer, primary_key=True, autoincrement=True)
        biz_id = Column(String, nullable=False)
        topic = Column(String, nullable=False)
        message = Column(String, nullable=False)
        status = Column(Enum(MessageStatus), default=MessageStatus.PENDING)
        retry_times = Column(Integer, default=0)
        max_retry = Column(Integer, default=3)
        next_retry_time = Column(DateTime, default=datetime.now)
        created_at = Column(DateTime, default=datetime.now)
        updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

# ========== 4. 初始化 ==========
logger = ContextLogger(__name__)

engine = create_engine(
    DATABASE_URL,
    isolation_level="READ COMMITTED",
    pool_recycle=300,
    future=True,
    pool_pre_ping=False,
    pool_size=50,
    max_overflow=25,
    echo=False
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 自动建表（仅开发测试用，生产请用迁移工具）
Base.metadata.create_all(bind=engine)

# ========== 5. 公共工具函数 ==========
def _ok(message: str = "操作成功", data: any = None) -> dict:
    return {"success": True, "message": message, "data": data}

def _fail(message: str, code: int = 400) -> dict:
    return {"success": False, "message": message, "code": code}
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@contextmanager
def get_db_session():
    session = SessionLocal()
    try:
        yield session
    except SQLAlchemyError as e:
        session.rollback()
        raise e
    finally:
        session.close()

def _update_cache(session, sku_id: str):
    if not redis_client:
        return
    inventory = session.execute(select(Inventory).where(Inventory.sku_id == sku_id)).scalars().first()
    if inventory:
        redis_client.setex(f"stock:available:{sku_id}", 300, inventory.available_stock)
        redis_client.setex(f"stock:locked:{sku_id}", 300, inventory.locked_stock)
        redis_client.setex(f"stock:total:{sku_id}", 300, inventory.total_stock)

def check_idempotent(session, biz_id: str) -> bool:
    if not biz_id:
        raise BusinessException("biz_id不能为空")
    existing = session.execute(
        select(InventoryLog.id).where(InventoryLog.biz_id == biz_id).limit(1)
    ).first()
    return existing is not None

def save_message(session, topic: str, msg: dict, biz_id: str):
    return save_message_with_retry_config(
        session=session,
        topic=topic,
        msg=msg,
        biz_id=biz_id,
        max_retry=MQ_CONFIG.get("retry_max_times", 3),
    )

def save_message_with_retry_config(session, topic: str, msg: dict, biz_id: str, max_retry: int = 3):
    msg_str = json.dumps(msg, ensure_ascii=False)
    try:
        existing_msg = session.execute(
            select(Message).where(Message.biz_id == biz_id)
        ).scalars().first()
        if existing_msg:
            logger.info(f"biz_id={biz_id}的消息已存在，跳过保存")
            return existing_msg.id

        next_retry_time = datetime.now() + timedelta(seconds=1)
        message = Message(
            biz_id=biz_id,
            topic=topic,
            message=msg_str,
            status=MessageStatus.PENDING,
            retry_times=0,
            max_retry=max_retry,
            next_retry_time=next_retry_time
        )
        session.add(message)
        session.flush()
        logger.info(f"保存MQ消息成功：ID={message.id}, biz_id={biz_id}, topic={topic}")
        return message.id
    except SQLAlchemyError as e:
        logger.warning(f"消息表结构或数据库异常，跳过消息落库 biz_id={biz_id}: {e}")
        return None

def send_message_with_retry(session, message_id: int):
    message = session.execute(
        select(Message).where(Message.id == message_id).with_for_update()
    ).scalars().first()
    if not message:
        logger.error(f"消息ID={message_id}不存在，跳过发送")
        return False
    if message.status == MessageStatus.SENT:
        logger.info(f"消息ID={message_id}已发送成功，跳过")
        return True
    if message.status == MessageStatus.FAILED:
        logger.info(f"消息ID={message_id}已达到重试上限，标记为失败")
        return False

    now = datetime.now()
    if message.next_retry_time > now:
        logger.info(f"消息ID={message_id}未到重试时间")
        return False

    try:
        message.status = MessageStatus.RETRYING
        session.flush()
        msg_content = json.loads(message.message)
        send_mq_msg(message.topic, msg_content)
        message.status = MessageStatus.SENT
        message.updated_at = datetime.now()
        logger.info(f"消息ID={message_id}发送成功")
        return True
    except Exception as e:
        message.retry_times += 1
        message.updated_at = datetime.now()
        if message.retry_times >= message.max_retry:
            message.status = MessageStatus.FAILED
            logger.error(f"消息ID={message_id}重试{message.retry_times}次失败，标记为永久失败: {e}")
        else:
            message.next_retry_time = now + timedelta(seconds=(message.retry_times + 1) * 2)
            message.status = MessageStatus.PENDING
            logger.warning(f"消息ID={message_id}发送失败，已重试{message.retry_times}次: {e}")
        session.flush()
        return False


def scan_and_retry_messages():
    logger.info("开始扫描待重试MQ消息...")
    # 先查询所有待重试消息（用临时Session）
    with get_db_session() as temp_session:
        pending_messages = temp_session.execute(
            select(Message).where(
                Message.status.in_([MessageStatus.PENDING, MessageStatus.RETRYING]),
                Message.retry_times < Message.max_retry,
                Message.next_retry_time <= datetime.now()
            )
        ).scalars().all()

    if not pending_messages:
        logger.info("无待重试消息")
        return

    success_count = fail_count = 0
    # 每条消息用独立Session，避免事务冲突
    for msg in pending_messages:
        try:
            with get_db_session() as session:
                with session.begin():  # 此时内层事务合法，因为是新Session
                    if send_message_with_retry(session, msg.id):
                        success_count += 1
                    else:
                        fail_count += 1
        except Exception as e:
            logger.error(f"重试消息ID={msg.id}时异常: {e}", exc_info=True)
            fail_count += 1

    logger.info(f"消息重试完成：成功{success_count}条，失败{fail_count}条")

def _check_optimistic_lock(session, sku_id: str, old_version: int) -> bool:
    try:
        result = session.execute(
            text(
                """
                UPDATE inventory
                SET version = version + 1
                WHERE sku_id = :sku_id AND version = :old_version
                """
            ),
            {"sku_id": sku_id, "old_version": old_version}
        )
        session.flush()
        return result.rowcount > 0
    except SQLAlchemyError as e:
        logger.error(f"乐观锁校验失败: {e}", exc_info=True)
        return False

# ========== 6. 公共锁执行函数 ==========
def execute_with_lock(
        sku_id: str,
        biz_id: str,
        lock_timeout: int,
        business_logic: Callable,
        ctx_logger,
        operation_type: str,
        **kwargs
) -> Dict:
    @observe_duration("inventory_operation_duration", tags={"operation_type": operation_type})
    def _execute():
        lock_key = f"inventory_lock:{sku_id}"
        try:
            with redis_lock(lock_key, lock_timeout) as token:
                if not token:
                    increment_counter("inventory_lock_failure", tags={"sku_id": sku_id})
                    ctx_logger.warning(f"获取分布式锁失败: {lock_key}")
                    return _fail("系统繁忙，请稍后重试")

                with get_db_session() as session:
                    with session.begin():
                        try:
                            if check_idempotent(session, biz_id):
                                ctx_logger.info(f"重复请求，biz_id={biz_id}，直接返回成功")
                                return _ok()

                            result = business_logic(session, ctx_logger, **kwargs)
                            if not result.get("success", False):
                                raise BusinessException(result.get("message", "业务失败"))

                            _update_cache(session, sku_id)
                            return result
                        except IntegrityError as e:
                            if "biz_id" in str(e):
                                ctx_logger.info(f"biz_id={biz_id} 唯一键冲突，幂等成功")
                                return _ok()
                            raise e
                        except SQLAlchemyError as e:
                            increment_counter("inventory_db_error", tags={"sku_id": sku_id})
                            ctx_logger.error(f"数据库异常: {e}", exc_info=True)
                            return _fail(f"数据库错误: {str(e)}")
        except RedisError as e:
            increment_counter("inventory_redis_error", tags={"sku_id": sku_id})
            ctx_logger.error(f"Redis异常: {e}", exc_info=True)
            return _fail("系统繁忙，请稍后重试")
        except BusinessException as e:
            ctx_logger.warning(f"业务异常: {e}")
            return _fail(str(e))
        except Exception as e:
            increment_counter("inventory_system_error", tags={"sku_id": sku_id})
            ctx_logger.error(f"系统异常: {e}", exc_info=True)
            return _fail(f"系统异常: {str(e)}")
    return _execute()

# ========== 7. 核心业务逻辑 ==========
def init_sku_stock(sku_id: str, total_stock: int, force: bool = False) -> Dict:
    trace_id = get_trace_id()
    ctx_logger = logger.with_context(trace_id=trace_id, sku_id=sku_id)
    force = True
    if not sku_id:
        return _fail("SKU ID不能为空")
    if total_stock < 0:
        return _fail("总库存不能为负数")

    biz_id = f"INIT_{sku_id}_{int(time.time())}" if force else f"INIT_{sku_id}"
    lock_timeout = REDIS_LOCK_EX

    def business_logic(session, ctx_logger, **kwargs):
        inventory = session.execute(
            select(Inventory).where(Inventory.sku_id == sku_id).with_for_update()
        ).scalars().first()

        is_new = inventory is None
        before_total = inventory.total_stock if inventory else 0
        before_available = inventory.available_stock if inventory else 0
        before_locked = inventory.locked_stock if inventory else 0

        if inventory:
            old_version = inventory.version
            inventory.total_stock = total_stock
            inventory.available_stock = total_stock
            inventory.locked_stock = 0
            if not _check_optimistic_lock(session, sku_id, old_version):
                raise BusinessException(f"库存版本冲突，SKU={sku_id}，请重试")
            ctx_logger.info(f"重置SKU {sku_id} 库存: {before_total} -> {total_stock}")
        else:
            inventory = Inventory(
                sku_id=sku_id,
                total_stock=total_stock,
                available_stock=total_stock,
                locked_stock=0,
                version=1
            )
            session.add(inventory)
            ctx_logger.info(f"新增SKU {sku_id} 库存，数量: {total_stock}")

        log = InventoryLog(
            sku_id=sku_id,
            order_id="INIT",
            biz_id=biz_id,
            change_type=ChangeType.INIT if is_new else ChangeType.RESET,
            change_amount=total_stock,
            before_total=before_total,
            before_available=before_available,
            before_locked=before_locked
        )
        session.add(log)
        return _ok(f"SKU {sku_id} 库存初始化成功")

    return execute_with_lock(
        sku_id=sku_id,
        biz_id=biz_id,
        lock_timeout=lock_timeout,
        business_logic=business_logic,
        ctx_logger=ctx_logger,
        operation_type="init"
    )

def _update_inventory_with_optimistic_lock(session, sku_id, old_version,
                                            total_delta=0, available_delta=0, locked_delta=0):
    """
    原子更新库存并递增版本号，返回是否更新成功（即版本匹配）
    """
    sql = text("""
        UPDATE inventory
        SET total_stock = total_stock + :total_delta,
            available_stock = available_stock + :available_delta,
            locked_stock = locked_stock + :locked_delta,
            version = version + 1,
            updated_at = :now
        WHERE sku_id = :sku_id AND version = :old_version
    """)
    result = session.execute(sql, {
        "sku_id": sku_id,
        "old_version": old_version,
        "total_delta": total_delta,
        "available_delta": available_delta,
        "locked_delta": locked_delta,
        "now": datetime.now()
    })
    session.flush()
    return result.rowcount > 0

ENABLE_REDIS_LOCK = True  # 压测时设为False，生产设为True


def lock_stock(sku_id: str, lock_num: int, order_id: str, lock_timeout: int = 30) -> Dict:
    trace_id = get_trace_id()
    ctx_logger = logger.with_context(trace_id=trace_id, sku_id=sku_id, order_id=order_id)

    # 基础参数校验
    if not sku_id or not order_id:
        return _fail("SKU ID和订单ID不能为空")
    if lock_num <= 0:
        return _fail("锁定数量必须大于0")

    biz_id = f"{order_id}_LOCK_{sku_id}"

    def business_logic(session: Session, ctx_logger, **kwargs):
        lock_num = kwargs.get("lock_num")
        # 加行锁查询库存（with_for_update保证行锁）
        inventory = session.execute(
            select(Inventory).where(Inventory.sku_id == sku_id).with_for_update()
        ).scalars().first()

        # 库存存在性校验
        if not inventory:
            return _fail(f"SKU {sku_id} 不存在")
        # 库存充足性校验
        if inventory.available_stock < lock_num:
            increment_counter("inventory_stock_shortage", tags={"sku_id": sku_id})
            return _fail(f"可用库存不足，当前可用: {inventory.available_stock}, 需要: {lock_num}")

        # 记录更新前的库存状态
        before_total = inventory.total_stock
        before_available = inventory.available_stock
        before_locked = inventory.locked_stock
        old_version = inventory.version

        # 执行乐观锁更新（修复参数冗余问题）
        success = _update_inventory_with_optimistic_lock(
            session,
            sku_id=sku_id,
            old_version=old_version,
            available_delta=-lock_num,  # 可用库存减少
            locked_delta=+lock_num  # 锁定库存增加
        )
        if not success:
            raise BusinessException(f"库存版本冲突，SKU={sku_id}，请重试")

        # 修复：日志的change_type应该是LOCK，不是RELEASE
        log = InventoryLog(
            sku_id=sku_id,
            order_id=order_id,
            biz_id=biz_id,
            change_type=ChangeType.LOCK,  # 核心修复：锁定库存而非释放
            change_amount=lock_num,
            before_total=before_total,
            before_available=before_available,
            before_locked=before_locked
        )
        session.add(log)

        # 构造MQ消息（通知订单超时解锁）
        mq_msg = {
            "trace_id": trace_id,
            "order_id": order_id,
            "sku_id": sku_id,
            "lock_num": lock_num,
            "create_time": int(time.time()),
            "timeout_seconds": MQ_CONFIG["order_timeout_seconds"]
        }
        save_message(session, MQ_CONFIG["order_timeout_topic"], mq_msg, biz_id)

        # 修复：返回文案改为“锁定成功”
        ctx_logger.info(f"锁定库存成功: SKU={sku_id}, 订单={order_id}, 数量={lock_num}")
        return _ok(f"锁定库存{lock_num}件成功")

    # ========== Redis锁逻辑优化 ==========
    if ENABLE_REDIS_LOCK:
        # 优化：缩小锁粒度（按SKU哈希分段，提升并发）
        lock_segment = hash(sku_id) % 10  # 分成10段锁
        lock_key = f"inventory_lock:{sku_id}:{lock_segment}"

        # 调用封装的Redis锁执行逻辑
        return execute_with_lock(
            lock_key=lock_key,  # 修复：原代码传sku_id，应该传锁key
            biz_id=biz_id,
            lock_timeout=lock_timeout,
            business_logic=business_logic,
            ctx_logger=ctx_logger,
            operation_type="lock",
            lock_num=lock_num
        )
    else:
        # 压测模式：跳过Redis锁，直接执行数据库逻辑
        session = SessionLocal()  # 直接创建数据库会话
        try:
            result = business_logic(session, ctx_logger, lock_num=lock_num)
            session.commit()
            return result
        except Exception as e:
            session.rollback()
            ctx_logger.error(f"锁定库存失败: {str(e)}", exc_info=True)
            return _fail(f"锁定库存失败: {str(e)}")
        finally:
            session.close()


def release_stock(sku_id: str, lock_num: int, order_id: str, lock_timeout: int = 30) -> Dict:
    trace_id = get_trace_id()
    ctx_logger = logger.with_context(trace_id=trace_id, sku_id=sku_id, order_id=order_id)

    if not sku_id or not order_id:
        return _fail("SKU ID和订单ID不能为空")
    if lock_num <= 0:
        return _fail("释放数量必须大于0")

    biz_id = f"{order_id}_RELEASE_{sku_id}"

    def business_logic(session, ctx_logger, **kwargs):
        lock_num = kwargs.get("lock_num")
        inventory = session.execute(
            select(Inventory).where(Inventory.sku_id == sku_id).with_for_update()
        ).scalars().first()

        if not inventory:
            return _fail(f"SKU {sku_id} 不存在")
        # 释放时检查锁定库存是否足够
        if inventory.locked_stock < lock_num:
            return _fail(f"锁定库存不足，当前锁定: {inventory.locked_stock}, 需要释放: {lock_num}")

        before_total = inventory.total_stock
        before_available = inventory.available_stock
        before_locked = inventory.locked_stock
        old_version = inventory.version

        # 原子更新：可用库存增加，锁定库存减少
        success = _update_inventory_with_optimistic_lock(
            session, sku_id, old_version,
            available_delta=+lock_num,
            locked_delta=-lock_num
        )
        if not success:
            raise BusinessException(f"库存版本冲突，SKU={sku_id}，请重试")

        # 记录操作日志
        log = InventoryLog(
            sku_id=sku_id,
            order_id=order_id,
            biz_id=biz_id,
            change_type=ChangeType.RELEASE,
            change_amount=lock_num,
            before_total=before_total,
            before_available=before_available,
            before_locked=before_locked
        )
        session.add(log)

        # 如果需要发送释放消息（可选），但注意这里不是锁定，所以通常不需要超时消息
        # 如果业务需要，可以取消下面的注释并修改 topic
        # mq_msg = {
        #     "trace_id": trace_id,
        #     "order_id": order_id,
        #     "sku_id": sku_id,
        #     "lock_num": lock_num,
        #     "create_time": int(time.time()),
        #     "timeout_seconds": MQ_CONFIG["order_timeout_seconds"]
        # }
        # save_message(session, MQ_CONFIG["order_timeout_topic"], mq_msg, biz_id)

        ctx_logger.info(f"释放库存成功: SKU={sku_id}, 订单={order_id}, 数量={lock_num}")
        return _ok(f"释放库存{lock_num}件成功")

    return execute_with_lock(
        sku_id=sku_id,
        biz_id=biz_id,
        lock_timeout=lock_timeout,
        business_logic=business_logic,
        ctx_logger=ctx_logger,
        operation_type="release",
        lock_num=lock_num
    )
def deduct_stock(sku_id: str, lock_num: int, order_id: str, lock_timeout: int = 30) -> Dict:
    trace_id = get_trace_id()
    ctx_logger = logger.with_context(trace_id=trace_id, sku_id=sku_id, order_id=order_id)

    if not sku_id or not order_id:
        return _fail("SKU ID和订单ID不能为空")
    if lock_num <= 0:
        return _fail("扣减数量必须大于0")

    biz_id = f"{order_id}_DEDUCT_{sku_id}"

    def business_logic(session, ctx_logger, **kwargs):
        lock_num = kwargs.get("lock_num")
        # 查询库存（加行锁，与分布式锁双重保障，但可保留）
        inventory = session.execute(
            select(Inventory).where(Inventory.sku_id == sku_id).with_for_update()
        ).scalars().first()

        if not inventory:
            return _fail(f"SKU {sku_id} 不存在")
        if inventory.locked_stock < lock_num:
            increment_counter("inventory_stock_shortage", tags={"sku_id": sku_id})
            return _fail(f"锁定库存不足，当前锁定: {inventory.locked_stock}, 需要扣减: {lock_num}")
        if inventory.total_stock < lock_num:
            return _fail(f"总库存不足，当前总库存: {inventory.total_stock}, 需要扣减: {lock_num}")

        # 记录操作前状态（用于日志）
        before_total = inventory.total_stock
        before_available = inventory.available_stock
        before_locked = inventory.locked_stock
        old_version = inventory.version

        # 单次原子更新：扣减总库存和锁定库存，可用库存不变
        success = _update_inventory_with_optimistic_lock(
            session, sku_id, old_version,
            total_delta=-lock_num,
            locked_delta=-lock_num,
            available_delta=0
        )
        if not success:
            raise BusinessException(f"库存版本冲突，SKU={sku_id}，请重试")

        # 记录操作日志
        log = InventoryLog(
            sku_id=sku_id,
            order_id=order_id,
            biz_id=biz_id,
            change_type=ChangeType.DEDUCT,
            change_amount=lock_num,
            before_total=before_total,
            before_available=before_available,
            before_locked=before_locked
        )
        session.add(log)

        # 发送补偿消息（支付失败重试）
        mq_msg = {
            "trace_id": trace_id,
            "order_id": order_id,
            "sku_id": sku_id,
            "deduct_num": lock_num,
            "create_time": int(time.time()),
            "retry_times": 0
        }
        save_message_with_retry_config(session, MQ_CONFIG["pay_callback_fail_topic"], mq_msg, biz_id, max_retry=3)

        ctx_logger.info(f"扣减总库存成功: SKU={sku_id}, 订单={order_id}, 数量={lock_num}")
        return _ok(f"扣减总库存{lock_num}件成功")

    # 调用统一锁执行器
    return execute_with_lock(
        sku_id=sku_id,
        biz_id=biz_id,
        lock_timeout=lock_timeout,
        business_logic=business_logic,
        ctx_logger=ctx_logger,
        operation_type="deduct",
        lock_num=lock_num
    )

def query_inventory(sku_id: str = None) -> Dict:
    trace_id = get_trace_id()
    ctx_logger = logger.with_context(trace_id=trace_id)
    try:
        with get_db_session() as session:
            if sku_id:
                inventory = session.execute(select(Inventory).where(Inventory.sku_id == sku_id)).scalars().first()
                if not inventory:
                    return _fail(f"SKU {sku_id} 不存在")
                return _ok("查询成功", {
                    "sku_id": inventory.sku_id,
                    "total_stock": inventory.total_stock,
                    "available_stock": inventory.available_stock,
                    "locked_stock": inventory.locked_stock,
                    "version": inventory.version
                })
            else:
                inventories = session.execute(select(Inventory)).scalars().all()
                return _ok("查询成功", [
                    {
                        "sku_id": inv.sku_id,
                        "total_stock": inv.total_stock,
                        "available_stock": inv.available_stock,
                        "locked_stock": inv.locked_stock,
                        "version": inv.version
                    } for inv in inventories
                ])
    except SQLAlchemyError as e:
        ctx_logger.error(f"查询库存失败", exc_info=True)
        return _fail(f"数据库错误: {str(e)}")

def query_inventory_log(
        sku_id: str = None,
        order_id: str = None,
        change_type: str = None,
        page: int = 1,
        page_size: int = 10
) -> Dict:
    trace_id = get_trace_id()
    ctx_logger = logger.with_context(trace_id=trace_id)
    page = max(1, page)
    page_size = max(1, min(page_size, 100))
    try:
        with get_db_session() as session:
            stmt = select(InventoryLog)
            if sku_id:
                stmt = stmt.where(InventoryLog.sku_id == sku_id)
            if order_id:
                stmt = stmt.where(InventoryLog.order_id == order_id)
            if change_type:
                stmt = stmt.where(InventoryLog.change_type == change_type)

            stmt = stmt.order_by(InventoryLog.created_at.desc())
            total = session.execute(stmt.with_only_columns(func.count())).scalar()
            logs = session.execute(stmt.offset((page-1)*page_size).limit(page_size)).scalars().all()

            return _ok("查询成功", {
                "list": [
                    {
                        "id": log.id,
                        "sku_id": log.sku_id,
                        "order_id": log.order_id,
                        "biz_id": log.biz_id,
                        "change_type": log.change_type,
                        "change_amount": log.change_amount,
                        "before_total": log.before_total,
                        "before_available": log.before_available,
                        "before_locked": log.before_locked,
                        "created_at": log.created_at.strftime("%Y-%m-%d %H:%M:%S")
                    } for log in logs
                ],
                "pagination": {
                    "page": page,
                    "page_size": page_size,
                    "total": total,
                    "total_pages": (total + page_size - 1) // page_size
                }
            })
    except SQLAlchemyError as e:
        ctx_logger.error(f"查询库存日志失败", exc_info=True)
        return _fail(f"数据库错误: {str(e)}")

# ========== 8. 新增聚合查询函数 ==========
def aggregate_inventory_logs(session=None) -> Dict:
    """
    聚合所有SKU的库存操作日志，计算每个SKU的理论总库存和锁定库存
    返回: {"success": bool, "data": {sku_id: {"total": int, "locked": int}, ...}, "message": str}
    """
    ctx = None  # 保存上下文对象
    need_close = False
    if session is None:
        ctx = get_db_session()
        session = ctx.__enter__()  # 手动进入上下文，获取session
        need_close = True
    try:
        query = session.query(
            InventoryLog.sku_id,
            func.sum(case(
                (InventoryLog.change_type == 'INIT', InventoryLog.change_amount),
                else_=0
            )).label('init_total'),
            func.sum(case(
                (InventoryLog.change_type == 'DEDUCT', InventoryLog.change_amount),
                else_=0
            )).label('deduct_total'),
            func.sum(case(
                (InventoryLog.change_type == 'LOCK', InventoryLog.change_amount),
                else_=0
            )).label('lock_total'),
            func.sum(case(
                (InventoryLog.change_type == 'RELEASE', InventoryLog.change_amount),
                else_=0
            )).label('release_total')
        ).group_by(InventoryLog.sku_id)

        results = query.all()
        agg_dict = {}
        for row in results:
            total_stock = row.init_total - row.deduct_total
            locked_stock = (row.lock_total - row.release_total) - row.deduct_total
            agg_dict[row.sku_id] = {"total": total_stock, "locked": locked_stock}

        # 使用统一的成功返回格式
        return _ok(data=agg_dict, message="聚合成功")
    except Exception as e:
        logger.error(f"聚合库存日志异常: {e}", exc_info=True)
        return _fail(message=f"聚合失败: {str(e)}")
    finally:
        if need_close and ctx:
            ctx.__exit__(None, None, None)# 手动退出上下文，关闭session

        # ========== 9. 重构后的对账函数 ==========
def reconcile_inventory():
    """定时对账：核对库存数据一致性（每天凌晨2点执行）"""
    def run():
        logger.info("库存对账服务已启动...")
        while True:
            try:
                current_time = time.localtime()
                if current_time.tm_hour == 2 and current_time.tm_min == 0:
                    logger.info("开始执行库存对账...")
                    # 1. 查询所有SKU当前库存
                    inventory_result = query_inventory()
                    if not inventory_result["success"]:
                        logger.error(f"查询库存失败，对账终止: {inventory_result['message']}")
                        time.sleep(60)
                        continue

                    sku_list = inventory_result["data"]

                    # 2. 一次性获取所有SKU的日志聚合结果
                    agg_result = aggregate_inventory_logs()
                    if not agg_result["success"]:
                        logger.error(f"聚合日志失败，对账终止: {agg_result['message']}")
                        time.sleep(60)
                        continue

                    agg_dict = agg_result["data"]  # {sku_id: {"total": x, "locked": y}}

                    # 3. 逐SKU对比实际值与理论值
                    for sku in sku_list:
                        sku_id = sku["sku_id"]
                        actual_total = sku["total_stock"]
                        actual_locked = sku["locked_stock"]
                        theory = agg_dict.get(sku_id, {"total": 0, "locked": 0})

                        if actual_total != theory["total"] or actual_locked != theory["locked"]:
                            logger.error(
                                f"库存对账异常: SKU{sku_id} "
                                f"实际总库存={actual_total}, 理论总库存={theory['total']} "
                                f"实际锁定库存={actual_locked}, 理论锁定库存={theory['locked']}"
                            )
                        else:
                            logger.info(f"库存对账正常: SKU{sku_id}")

                    logger.info("库存对账完成")
                    time.sleep(3600)  # 避免重复执行
                else:
                    time.sleep(60)
            except Exception as e:
                logger.error(f"库存对账服务异常: {e}")
                time.sleep(300)

    t = threading.Thread(target=run, daemon=True)
    t.start()

# ========== 10. 启动所有补偿服务 ==========
def start_all_compensate_services():
    """启动所有补偿和对账服务"""
    #如果需要，可以在这里启动其他补偿线程
    #compensate_order_timeout()
    #compensate_pay_callback_fail()
    reconcile_inventory()
    logger.info("所有补偿和对账服务已启动")

# ========== 11. 消息补偿定时任务（可选） ==========
if __name__ == "__main__":
    import time
    if os.getenv("RUN_MESSAGE_RETRY", "true") == "true":
        logger.info("启动MQ消息补偿定时任务...")
        while True:
            try:
                scan_and_retry_messages()
            except Exception as e:
                logger.error("消息补偿任务执行异常", exc_info=True)
            time.sleep(10)
__all__ = [
    'Base', 'get_db', 'get_db_session',
    'init_sku_stock', 'lock_stock', 'release_stock', 'deduct_stock',
    'query_inventory', 'query_inventory_log', 'reconcile_inventory'
] # 可选，但确保 Base 可导入