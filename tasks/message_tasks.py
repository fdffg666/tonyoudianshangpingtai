# tasks/message_tasks.py
from celery import Celery
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from utils.config import DATABASE_URL, MQ_CONFIG
from models.message import Message
from utils.mq import send_mq_msg
import json
from utils.logger import ContextLogger  # 补充导入日志（已有修复的ContextLogger）

# 初始化Celery（你的原有逻辑，已适配修复后的MQ_CONFIG）
celery_app = Celery("message_tasks", broker=MQ_CONFIG["broker_url"])

# 初始化数据库连接（原有逻辑）
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)

# 初始化日志
logger = ContextLogger(__name__)


@celery_app.task(bind=True, max_retries=3)
def send_pending_messages(self):
    """
    定时扫表发送待发送消息（修复JSON解析+事务优化）
    """
    session = SessionLocal()
    try:
        # 批量查询待发送消息（原有逻辑）
        messages = session.execute(
            select(Message).where(
                Message.status == "PENDING",
                Message.retry_times < 3
            ).limit(100)
        ).scalars().all()

        for msg in messages:
            try:
                # 核心修复1：捕获JSON解析异常，避免单条消息失败中断全批
                try:
                    msg_dict = json.loads(msg.message)
                except json.JSONDecodeError as e:
                    # JSON解析失败：标记为死信，不再重试
                    logger.error(f"消息JSON解析失败（标记为死信）：msg_id={msg.id}, error={e}", exc_info=True)
                    msg.status = "DEAD_LETTER"
                    msg.message = f"JSON_DECODE_ERROR: {str(e)}\nORIGINAL_MSG: {msg.message}"
                    session.flush()  # 刷入数据库，不中断循环
                    continue  # 跳过这条，处理下一条

                # 发送MQ消息（原有逻辑）
                send_mq_msg(msg.topic, msg_dict)

                # 更新状态为已发送（原有逻辑）
                msg.status = "SENT"
                logger.info(f"消息发送成功：msg_id={msg.id}, topic={msg.topic}")
                session.flush()  # 核心修复2：循环内flush，最后统一commit

            except Exception as e:
                # 发送失败，重试次数+1（原有逻辑优化）
                msg.retry_times += 1
                if msg.retry_times >= 3:
                    msg.status = "FAILED"
                    logger.error(f"消息重试达上限（标记为失败）：msg_id={msg.id}, error={e}", exc_info=True)
                else:
                    logger.warning(f"消息发送失败（重试{msg.retry_times}次）：msg_id={msg.id}, error={e}")
                session.flush()  # 刷入数据库，不中断循环

        # 核心修复3：批量commit，避免循环内逐条commit的性能问题
        session.commit()

    except Exception as e:
        session.rollback()
        logger.error(f"批量发送消息异常：{e}", exc_info=True)
        raise e
    finally:
        session.close()