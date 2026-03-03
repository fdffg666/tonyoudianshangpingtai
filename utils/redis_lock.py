# utils/redis_lock.py
import uuid
import logging
import threading
import time
from contextlib import contextmanager
import redis
from redis.exceptions import RedisError
from utils.config import REDIS_CONFIG, REDIS_LOCK_EX  # 改成 REDIS_CONFIG

logger = logging.getLogger(__name__)

# Redis 连接池（保留你的优点）
redis_pool = redis.ConnectionPool(
    host=REDIS_CONFIG["host"],
    port=REDIS_CONFIG["port"],
    db=REDIS_CONFIG["db"],
    decode_responses=True,
    max_connections=20
)
redis_client = redis.Redis(connection_pool=redis_pool)


@contextmanager
def redis_lock(
        lock_key: str,
        timeout: int = REDIS_LOCK_EX,
        retry_times: int = 30,  # 新增：重试次数
        retry_interval: float = 1,  # 新增：重试间隔（秒）
        watch_dog: bool = True  # 新增：是否开启看门狗续期
):
    """
    Redis分布式锁上下文管理器（增强版：看门狗续期+重试机制）
    :param lock_key: 锁的唯一标识
    :param timeout: 锁过期时间
    :param retry_times: 获取锁失败的重试次数
    :param retry_interval: 重试间隔
    :param watch_dog: 是否开启看门狗续期
    """
    token = str(uuid.uuid4())
    lock_acquired = False
    watch_dog_thread = None
    stop_watch_dog = threading.Event()

    def _watch_dog_task():
        """看门狗续期任务：每隔 timeout/3 续期一次"""
        while not stop_watch_dog.is_set():
            try:
                # 检查锁是否还属于自己
                current_token = redis_client.get(lock_key)
                if current_token == token:
                    # 续期
                    redis_client.expire(lock_key, timeout)
                    logger.debug(f"看门狗续期成功: {lock_key}")
                else:
                    # 锁已经不属于自己了，停止续期
                    logger.warning(f"锁已被其他线程获取，停止看门狗: {lock_key}")
                    break
            except RedisError as e:
                logger.error(f"看门狗续期失败: {e}")
            # 每隔 timeout/3 续期一次
            time.sleep(timeout / 3)

    try:
        # 新增：重试获取锁
        for i in range(retry_times + 1):
            # SET NX EX 原子操作获取锁（保留你的优点）
            lock_acquired = redis_client.set(lock_key, token, nx=True, ex=timeout)
            if lock_acquired:
                logger.debug(f"获取锁成功: {lock_key}, 尝试次数: {i + 1}")
                break
            if i < retry_times:
                logger.debug(f"获取锁失败，等待重试: {lock_key}, 尝试次数: {i + 1}")
                time.sleep(retry_interval)

        if not lock_acquired:
            logger.warning(f"获取锁失败，已达最大重试次数: {lock_key}")
            yield None
        else:
            # 新增：启动看门狗续期
            if watch_dog:
                watch_dog_thread = threading.Thread(target=_watch_dog_task, daemon=True)
                watch_dog_thread.start()
                logger.debug(f"看门狗已启动: {lock_key}")

            yield token
    finally:
        # 停止看门狗
        if watch_dog_thread:
            stop_watch_dog.set()
            watch_dog_thread.join(timeout=1)

        # 只有获取到锁才释放，且只能释放自己的锁（保留你的优点）
        if lock_acquired:
            try:
                # LUA脚本保证原子性（保留你的优点）
                script = """
                if redis.call("get", KEYS[1]) == ARGV[1] then
                    return redis.call("del", KEYS[1])
                else
                    return 0
                end
                """
                redis_client.eval(script, 1, lock_key, token)
                logger.debug(f"释放锁成功: {lock_key}")
            except RedisError as e:
                logger.error(f"释放锁失败: {e}")