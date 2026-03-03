# utils/logger.py
import logging
import uuid

class ContextLogger:
    def __init__(self, name):
        """创建带上下文能力的日志封装。"""
        self.logger = logging.getLogger(name)
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )

    def with_context(self, **kwargs):
        """返回带追加上下文的 logger（当前实现为兼容返回自身）。"""
        return self

    def info(self, msg):
        """记录 info 级别日志。"""
        self.logger.info(msg)

    def warning(self, msg):
        """记录 warning 级别日志。"""
        self.logger.warning(msg)

    # 👇 核心修复：加上 exc_info=False，兼容所有调用
    def error(self, msg, exc_info=False):
        """记录 error 级别日志，支持异常栈输出。"""
        self.logger.error(msg, exc_info=exc_info)


def get_trace_id():
    """生成短 trace_id 供链路追踪与日志关联。"""
    return str(uuid.uuid4())[:8]