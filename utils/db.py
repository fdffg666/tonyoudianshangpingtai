# utils/db.py
import os
import sqlite3
import threading
import logging
from contextlib import contextmanager

logger = logging.getLogger(__name__)

# 线程本地存储，用于每个线程独立的数据库连接
_local = threading.local()

# 默认数据库文件路径，可通过环境变量覆盖
DEFAULT_DB_FILE = "inventory_test.db"
DB_FILE = os.getenv("TEST_DB_FILE", DEFAULT_DB_FILE)


def get_db_connection():
    """
    获取当前线程的数据库连接（每个线程独立）。
    如果连接不存在，则创建新连接。
    """
    if not hasattr(_local, 'connection'):
        try:
            conn = sqlite3.connect(
                DB_FILE,
                check_same_thread=False,  # 允许跨线程使用（需确保线程安全）
                timeout=30,
                isolation_level=None      # 自动提交模式，便于事务控制
            )
            conn.row_factory = sqlite3.Row  # 返回字典形式的结果
            _local.connection = conn
            logger.debug(f"Created new SQLite connection for thread {threading.get_ident()}")
        except sqlite3.Error as e:
            logger.error(f"Failed to connect to database {DB_FILE}: {e}")
            raise
    return _local.connection


def close_db_connection():
    """关闭当前线程的数据库连接（可选，用于资源清理）"""
    if hasattr(_local, 'connection'):
        try:
            _local.connection.close()
            logger.debug(f"Closed SQLite connection for thread {threading.get_ident()}")
        except sqlite3.Error as e:
            logger.error(f"Error closing connection: {e}")
        finally:
            del _local.connection


@contextmanager
def get_db_session():
    """
    获取数据库会话（上下文管理器），自动提交/回滚事务。
    用法：
        with get_db_session() as cursor:
            cursor.execute(...)
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        yield cursor
        conn.commit()
        logger.debug("Transaction committed")
    except Exception as e:
        conn.rollback()
        logger.error(f"Transaction rolled back due to: {e}")
        raise
    finally:
        cursor.close()


def init_db():
    """
    初始化数据库表结构，创建必要的表和索引。
    如果表已存在，不会重复创建。
    """
    with get_db_session() as cursor:
        # 创建库存表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS inventory (
                sku_id TEXT PRIMARY KEY,
                total_stock INTEGER NOT NULL DEFAULT 0,
                available_stock INTEGER NOT NULL DEFAULT 0,
                locked_stock INTEGER NOT NULL DEFAULT 0,
                create_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                update_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        # 创建索引
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_inventory_update ON inventory(update_time)')

        # 创建库存锁定记录表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS inventory_lock (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sku_id TEXT NOT NULL,
                order_id TEXT NOT NULL,
                lock_num INTEGER NOT NULL,
                lock_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(sku_id, order_id)
            )
        ''')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_lock_sku ON inventory_lock(sku_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_lock_order ON inventory_lock(order_id)')

        logger.info("Database tables initialized successfully.")


# 程序退出时清理所有连接（可选，适用于单线程应用）
import atexit

def _close_all_connections():
    """关闭所有线程的连接（谨慎使用，仅适合简单脚本）"""
    # 实际应用中，每个线程应自行管理连接
    pass  # 此处留空，因为线程本地连接无法全局遍历

# 如果需要支持多线程，建议在应用生命周期结束时统一清理，但更推荐线程自行管理。

if __name__ == "__main__":
    # 设置日志格式
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    init_db()
    print("数据库初始化完成")