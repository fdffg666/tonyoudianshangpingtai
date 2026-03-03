# utils/metrics.py
from prometheus_client import Counter, Histogram
import time

# 定义监控指标
INVENTORY_LOCK_FAILURE = Counter(
    "inventory_lock_failure_total",
    "获取分布式锁失败次数",
    ["sku_id"]
)
INVENTORY_STOCK_SHORTAGE = Counter(
    "inventory_stock_shortage_total",
    "库存不足次数",
    ["sku_id"]
)
INVENTORY_DB_ERROR = Counter(
    "inventory_db_error_total",
    "数据库异常次数",
    ["sku_id"]
)
INVENTORY_REDIS_ERROR = Counter(
    "inventory_redis_error_total",
    "Redis异常次数",
    ["sku_id"]
)
INVENTORY_SYSTEM_ERROR = Counter(
    "inventory_system_error_total",
    "系统异常次数",
    ["sku_id"]
)
INVENTORY_OPERATION_DURATION = Histogram(
    "inventory_operation_duration_seconds",
    "库存操作耗时",
    ["operation_type"]
)

def increment_counter(metric_name: str, tags: dict = None):
    """
    增加计数器
    """
    tags = tags or {}
    if metric_name == "inventory_lock_failure":
        INVENTORY_LOCK_FAILURE.labels(**tags).inc()
    elif metric_name == "inventory_stock_shortage":
        INVENTORY_STOCK_SHORTAGE.labels(**tags).inc()
    elif metric_name == "inventory_db_error":
        INVENTORY_DB_ERROR.labels(**tags).inc()
    elif metric_name == "inventory_redis_error":
        INVENTORY_REDIS_ERROR.labels(**tags).inc()
    elif metric_name == "inventory_system_error":
        INVENTORY_SYSTEM_ERROR.labels(**tags).inc()

def observe_duration(metric_name: str, tags: dict = None):
    """
    记录耗时（装饰器）
    """
    tags = tags or {}
    def decorator(func):
        def wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                return func(*args, **kwargs)
            finally:
                duration = time.time() - start_time
                if metric_name == "inventory_operation_duration":
                    INVENTORY_OPERATION_DURATION.labels(**tags).observe(duration)
        return wrapper
    return decorator