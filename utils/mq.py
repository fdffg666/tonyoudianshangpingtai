# utils/mq.py
import redis
import json
from utils.config import REDIS_CONFIG, MQ_CONFIG

# 初始化Redis客户端
redis_client = redis.Redis(**REDIS_CONFIG)

def send_mq_msg(topic: str, msg: dict):
    """发送MQ消息（Redis List模拟）"""
    try:
        redis_client.rpush(topic, json.dumps(msg))
        return True
    except Exception as e:
        print(f"发送MQ消息失败: {e}")
        return False

def consume_mq_msg(topic: str, timeout: int = 10):
    """消费MQ消息（阻塞式）"""
    try:
        msg = redis_client.blpop(topic, timeout=timeout)
        if msg:
            return json.loads(msg[1])
        return None
    except Exception as e:
        print(f"消费MQ消息失败: {e}")
        return None

def get_msg_len(topic: str) -> int:
    """获取MQ队列长度（用于监控）"""
    try:
        return redis_client.llen(topic)
    except Exception as e:
        print(f"获取队列长度失败: {e}")
        return 0