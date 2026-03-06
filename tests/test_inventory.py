# ========== 强制添加项目根路径（修复路径稳定性） ==========
import sys
import os
import time
import threading
from typing import List, Tuple
from contextlib import suppress
import traceback  # 提前导入，全局可用
import uuid
import logging

# 硬编码根路径，杜绝路径拼接失败
PROJECT_ROOT = "C:/Users/时柒/PycharmProjects/PythonProject"
sys.path.append(PROJECT_ROOT)
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))

# ========== 导入修正 + 兼容修复（核心改这里） ==========
try:
    from services.inventory_service import (
        init_sku_stock,
        lock_stock,
        release_stock,
        deduct_stock,
        query_inventory,
        query_inventory_log
    )
except ImportError as e:
    raise RuntimeError(f"导入核心库存模块失败：{e}\n请检查services/inventory_service.py是否存在") from e

# 修复ContextLogger的exc_info参数问题
try:
    from utils.logger import ContextLogger, get_trace_id
    from utils.exceptions import BusinessException, SystemException
except ImportError:
    # 重新实现ContextLogger，完善exc_info参数支持
    class ContextLogger:
        def __init__(self, name):
            self.name = name
            self._logger = logging.getLogger(name)
            # 初始化日志格式
            logging.basicConfig(
                level=logging.INFO,
                format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                handlers=[logging.StreamHandler()]
            )

        def with_context(self, **kwargs):
            # 模拟上下文，直接返回自身
            return self

        def info(self, msg):
            self._logger.info(msg)

        def warning(self, msg):
            self._logger.warning(msg)

        def error(self, msg, exc_info=False):  # 完善exc_info支持
            if exc_info:
                self._logger.error(msg, exc_info=True)
            else:
                self._logger.error(msg)


    def get_trace_id():
        return str(uuid.uuid4())[:8]


    class BusinessException(Exception):
        pass


    class SystemException(Exception):
        pass

# ========== 全局配置 ==========
logger = ContextLogger(__name__)
TEST_SKU_ID = "SKU_TEST_001"
TEST_ORDER_ID = "ORDER_1001"
TEST_STOCK_NUM = 10
TEST_LOCK_NUM = 2
TEST_RELEASE_NUM = 1
TEST_DEDUCT_NUM = 1
CONCURRENT_THREADS = 5
CONCURRENT_LOCK_NUM = 1
LOCK_TIMEOUT = 30

# 线程锁（解决并发测试结果收集的线程安全问题）
result_lock = threading.Lock()


# ========== 测试结果类 ==========
class TestResult:
    def __init__(self, name: str, success: bool, message: str, data: dict = None):
        self.name = name
        self.success = success
        self.message = message
        self.data = data
        self.trace_id = get_trace_id()
        self.exec_time = time.time()

    def to_dict(self):
        return {
            "测试用例": self.name,
            "结果": "✅ 通过" if self.success else "❌ 失败",
            "trace_id": self.trace_id,
            "消息": self.message,
            "数据": self.data
        }


# ========== 核心工具函数（修复两个关键错误） ==========
def safe_clear_test_data(sku_id: str) -> bool:
    """安全清理测试数据（修复rowcount和exc_info问题）"""
    if not sku_id or sku_id == "*":
        logger.error(f"禁止清理SKU={sku_id}的Data，存在删库风险")
        return False

    try:
        from services.inventory_service import get_db_session
        from models.inventory import Inventory, InventoryLog
        from models.message import Message

        with get_db_session() as session:
            with session.begin():
                # 修复错误1：SQLAlchemy 2.0+ 用count()替代rowcount
                count = session.query(Inventory).filter(Inventory.sku_id == sku_id).count()
                if count == 0:
                    logger.info(f"📌 无测试数据可清理: SKU={sku_id}")
                    return True

                # 批量删除测试数据（添加容错）
                del_inventory = session.query(Inventory).filter(Inventory.sku_id == sku_id).delete()
                del_log = session.query(InventoryLog).filter(InventoryLog.sku_id == sku_id).delete()

                # 消息表删除加容错
                with suppress(Exception):
                    del_message = session.query(Message).filter(Message.biz_id.like(f"%{sku_id}%")).delete()

        logger.info(f"🧹 安全清理测试数据完成: SKU={sku_id}, 清理库存记录数={count}, 日志记录数={del_log}")
        return True
    except Exception as e:
        # 修复错误2：完善异常栈打印
        error_detail = f"{str(e)}\n{traceback.format_exc()}"
        logger.error(f"❌ 清理测试数据失败: {error_detail}")
        return False


def run_test_case(test_name: str, func, *args, **kwargs) -> TestResult:
    """执行单个测试用例（完善异常处理）"""
    trace_id = get_trace_id()
    ctx_logger = logger.with_context(trace_id=trace_id)
    try:
        ctx_logger.info(f"🚀 开始执行测试用例: {test_name} [trace_id={trace_id}]")
        result = func(*args, **kwargs)

        # 统一结果格式（兼容不同返回值）
        if isinstance(result, dict):
            success = result.get("success", False)
            message = result.get("message", "")
            data = result.get("data")
        else:
            success = False
            message = f"用例返回格式错误: {type(result)}"
            data = None

        test_result = TestResult(test_name, success, message, data)
        ctx_logger.info(f"✅ 测试用例完成: {test_name} [trace_id={trace_id}]")
        return test_result

    except (BusinessException, SystemException) as e:
        ctx_logger.error(f"❌ 测试用例业务异常: {test_name} | {e}", exc_info=True)
        return TestResult(test_name, False, f"业务异常: {str(e)}")

    except Exception as e:
        # 完善系统异常打印
        error_detail = f"{str(e)}\n{traceback.format_exc()}"
        ctx_logger.error(f"❌ 测试用例系统异常: {test_name} | {error_detail}")
        return TestResult(test_name, False, f"系统异常: {str(e)}")


def print_test_summary(results: List[TestResult]):
    """打印测试汇总（优化格式）"""
    logger.info("\n" + "=" * 80)
    logger.info("📊 库存管理系统 - 测试结果汇总")
    logger.info("=" * 80)

    total = len(results)
    passed = len([r for r in results if r.success])
    failed = total - passed
    pass_rate = (passed / total) * 100 if total > 0 else 0

    logger.info(f"📈 总体统计: 总用例数={total} | 通过={passed} | 失败={failed} | 通过率={pass_rate:.2f}%")
    logger.info("-" * 80)

    # 打印失败用例详情
    if failed > 0:
        logger.error("❌ 失败用例详情:")
        for r in results:
            if not r.success:
                logger.error(f"  - {r.name} (trace_id={r.trace_id}): {r.message}")
    else:
        logger.info("🎉 恭喜！所有测试用例全部通过！")

    logger.info("=" * 80 + "\n")


# ========== 并发测试函数（修复线程安全问题） ==========
def concurrent_lock_test(sku_id: str, order_id_prefix: str, lock_num: int, thread_num: int):
    """并发锁定测试（添加线程锁，确保结果收集安全）"""
    results = []

    def worker(thread_id):
        order_id = f"{order_id_prefix}_CONCURRENT_{thread_id}"
        test_result = run_test_case(
            f"并发锁定库存-线程{thread_id}",
            lock_stock,
            sku_id, lock_num, order_id, LOCK_TIMEOUT
        )
        # 线程安全的结果添加
        with result_lock:
            results.append(test_result)
        logger.info(f"🧵 线程{thread_id}执行完成: {test_result.to_dict()['结果']}")

    # 启动线程
    threads = []
    logger.info(f"🚦 启动{thread_num}个并发线程测试库存锁定...")
    for i in range(thread_num):
        t = threading.Thread(target=worker, args=(i + 1,))
        threads.append(t)
        t.start()

    # 等待所有线程完成
    for t in threads:
        t.join(timeout=60)  # 添加超时，防止线程挂起

    logger.info(f"🏁 所有{thread_num}个并发线程执行完成")
    return results


# ========== 核心测试流程 ==========
def run_full_test():
    """执行全量测试流程"""
    root_trace_id = get_trace_id()
    ctx_logger = logger.with_context(trace_id=root_trace_id)
    ctx_logger.info("=== 开始库存管理核心功能全量测试 [trace_id={}] ===".format(root_trace_id))

    all_results = []

    # 1. 安全清理历史数据
    clear_success = safe_clear_test_data(TEST_SKU_ID)
    all_results.append(TestResult("安全清理测试数据", clear_success, "清理成功" if clear_success else "清理失败"))

    # 2. 基础功能测试
    all_results.append(run_test_case("初始化库存", init_sku_stock, TEST_SKU_ID, TEST_STOCK_NUM))
    all_results.append(
        run_test_case(f"锁定{TEST_LOCK_NUM}件库存", lock_stock, TEST_SKU_ID, TEST_LOCK_NUM, TEST_ORDER_ID,
                      LOCK_TIMEOUT))
    all_results.append(
        run_test_case(f"释放{TEST_RELEASE_NUM}件库存", release_stock, TEST_SKU_ID, TEST_RELEASE_NUM, TEST_ORDER_ID,
                      LOCK_TIMEOUT))
    all_results.append(
        run_test_case(f"扣减{TEST_DEDUCT_NUM}件总库存", deduct_stock, TEST_SKU_ID, TEST_DEDUCT_NUM, TEST_ORDER_ID,
                      LOCK_TIMEOUT))
    all_results.append(
        run_test_case("测试库存不足", lock_stock, TEST_SKU_ID, TEST_STOCK_NUM + 1, f"{TEST_ORDER_ID}_SHORTAGE",
                      LOCK_TIMEOUT))
    all_results.append(run_test_case("查询单个SKU库存", query_inventory, TEST_SKU_ID))
    all_results.append(run_test_case("查询所有SKU库存", query_inventory))
    all_results.append(run_test_case("查询指定订单的库存日志", query_inventory_log, order_id=TEST_ORDER_ID))
    all_results.append(
        run_test_case("查询指定SKU的库存日志（分页）", query_inventory_log, sku_id=TEST_SKU_ID, page_size=5))

    # 3. 幂等性测试
    all_results.append(
        run_test_case("测试幂等性（重复锁定）", lock_stock, TEST_SKU_ID, TEST_LOCK_NUM, TEST_ORDER_ID, LOCK_TIMEOUT))
    all_results.append(
        run_test_case("测试幂等性（重复释放）", release_stock, TEST_SKU_ID, TEST_RELEASE_NUM, TEST_ORDER_ID,
                      LOCK_TIMEOUT))
    all_results.append(
        run_test_case("测试幂等性（重复扣减）", deduct_stock, TEST_SKU_ID, TEST_DEDUCT_NUM, TEST_ORDER_ID, LOCK_TIMEOUT))

    # 4. 边界值测试（添加容错）
    all_results.append(run_test_case("测试边界值-库存为0初始化", init_sku_stock, "SKU_TEST_002", 0))
    all_results.append(
        run_test_case("测试边界值-扣减等于锁定库存", deduct_stock, TEST_SKU_ID, 1, f"{TEST_ORDER_ID}_BOUNDARY",
                      LOCK_TIMEOUT))
    all_results.append(run_test_case("测试边界值-SKU为空", init_sku_stock, "", 10))

    # 5. 高并发测试
    concurrent_results = concurrent_lock_test(TEST_SKU_ID, TEST_ORDER_ID, CONCURRENT_LOCK_NUM, CONCURRENT_THREADS)
    all_results.extend(concurrent_results)

    # 6. 打印汇总结果
    print_test_summary(all_results)

    ctx_logger.info("=== 测试流程结束 [trace_id={}] ===".format(root_trace_id))


if __name__ == "__main__":
    # 主函数入口（确保所有依赖已加载）
    try:
        run_full_test()
    except Exception as e:
        logger.error(f"❌ 测试流程整体异常: {str(e)}", exc_info=True)
        sys.exit(1)