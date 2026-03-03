# ========== 强制添加项目根路径（解决导入问题） ==========
import sys
import os
import uuid
import logging
import threading
import time
from typing import Dict, List, Tuple

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.append(PROJECT_ROOT)

# 确保在sys.path设置后导入业务模块
from services.inventory_service import init_sku_stock, lock_stock, query_inventory
# =======================================================

# 配置日志输出
# 使用logging替代print，方便集成到CI/CD或日志系统
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# 压测配置
RUN_ID = uuid.uuid4().hex[:8]
TEST_SKU_ID = f"SKU_TEST_{RUN_ID}"  # 每次运行使用唯一SKU，避免幂等日志冲突
TOTAL_STOCK = 100  # 初始化总库存
CONCURRENT_NUM = 20  # 增加并发请求数，测试超卖风险
LOCK_NUM_PER_REQUEST = 5  # 每个请求锁定数量

# 并发控制
# Barrier设为 N+1，包含N个工作线程 + 1个主线程
start_barrier = threading.Barrier(CONCURRENT_NUM + 1)
result_lock = threading.Lock()
results: List[Dict] = []


def concurrent_lock_task(order_id: str):
    """
    单个并发任务：尝试锁定库存并记录结构化结果。

    Args:
        order_id (str): 模拟的订单ID，用于幂等��验
    """
    result = {}
    try:
        # 等待所有线程就绪，确保同时触发
        start_barrier.wait()

        # 执行核心锁定逻辑
        start_time = time.perf_counter()
        result = lock_stock(TEST_SKU_ID, LOCK_NUM_PER_REQUEST, order_id)
        elapsed = time.perf_counter() - start_time

        # 记录耗时
        result["elapsed_ms"] = elapsed * 1000

    except threading.BrokenBarrierError:
        return
    except Exception as e:
        result = {"success": False, "message": f"线程异常: {str(e)}", "elapsed_ms": 0}
        logger.error(f"任务执行异常: {e}", exc_info=True)

    with result_lock:
        results.append({
            "order_id": order_id,
            "success": bool(result.get("success")),
            "message": result.get("message", ""),
            "elapsed_ms": result.get("elapsed_ms", 0)
        })


def summarize_and_validate(total_time: float) -> int:
    """
    汇总压测结果并进行核心逻辑校验。

    1. 校验成功数与失败数是否合理
    2. 校验库存数据是否守恒
    3. 校验是否有异常失败原因

    Args:
        total_time (float): 压测总耗时

    Returns:
        int: 0 表示通过，1 表示失败
    """
    success_items = [r for r in results if r["success"]]
    fail_items = [r for r in results if not r["success"]]
    success_count = len(success_items)
    fail_count = len(fail_items)

    inv_result = query_inventory(TEST_SKU_ID)
    inv_data = inv_result.get("data") if inv_result.get("success") else None

    logger.info("\n=== 压测结果汇总 ===")
    logger.info(f"总耗时：{total_time:.4f} 秒 (TPS: {CONCURRENT_NUM / total_time:.2f})")
    logger.info(f"总请求数：{CONCURRENT_NUM} 个")
    logger.info(f"成功锁定：{success_count} 个")
    logger.info(f"失败拦截：{fail_count} 个")

    if inv_data:
        logger.info(
            f"库存快照：总数={inv_data['total_stock']} | 可用={inv_data['available_stock']} | 锁定={inv_data['locked_stock']}"
        )

    # 核心校验项
    checks: List[Tuple[str, bool]] = []

    # 1. 请求完整性校验
    checks.append(("请求总数一致", success_count + fail_count == CONCURRENT_NUM))

    # 2. 超卖校验（最核心）
    max_possible_success = TOTAL_STOCK // LOCK_NUM_PER_REQUEST
    checks.append(("未发生超卖", success_count <= max_possible_success))

    # 3. 失败原因纯洁性校验
    allowed_errors = ["库存不足", "系统繁忙", "获取分布式锁失败"]
    abnormal_fail = [
        r for r in fail_items
        if not any(err in r["message"] for err in allowed_errors)
    ]
    checks.append(("无异常报错", len(abnormal_fail) == 0))

    # 4. 库存数据一致性校验
    if inv_data:
        expected_locked = success_count * LOCK_NUM_PER_REQUEST
        expected_available = TOTAL_STOCK - expected_locked

        checks.append(("锁定库存数正确", inv_data["locked_stock"] == expected_locked))
        checks.append(("可用库存数正确", inv_data["available_stock"] == expected_available))
        checks.append(("数据守恒", inv_data["available_stock"] + inv_data["locked_stock"] == inv_data["total_stock"]))
    else:
        checks.append(("库存查询成功", False))

    logger.info("\n=== 判定项 ===")
    all_passed = True
    for name, passed in checks:
        icon = '✅' if passed else '❌'
        logger.info(f"{icon} {name}")
        if not passed:
            all_passed = False

    if abnormal_fail:
        logger.error("\n异常失败样例（前5条）：")
        for item in abnormal_fail[:5]:
            logger.error(f"- {item['order_id']}: {item['message']}")

    return 0 if all_passed else 1


def main():
    """压测主入口"""
    logger.info("=== 库存防超卖并发压测开始 ===")
    logger.info(f"测试配置：总库存={TOTAL_STOCK}件 | 并发数={CONCURRENT_NUM} | 单次锁定={LOCK_NUM_PER_REQUEST}")

    # 1. 初始化库存
    init_result = init_sku_stock(TEST_SKU_ID, TOTAL_STOCK, force=True)
    if not init_result.get("success"):
        logger.error(f"初始化库存失败：{init_result.get('message')}")
        sys.exit(1)
    logger.info(f"1. 初始化库存完成：SKU={TEST_SKU_ID}")

    # 2. 准备线程
    threads = []
    for i in range(CONCURRENT_NUM):
        order_id = f"TEST_ORDER_{RUN_ID}_{i + 1}"
        t = threading.Thread(target=concurrent_lock_task, args=(order_id,))
        threads.append(t)
        t.start()

    logger.info("2. 线程准备就绪，开始并发...")

    # 3. 触发并发
    try:
        start_time = time.perf_counter()
        start_barrier.wait(timeout=10) # 设置超时防止死锁

        for t in threads:
            t.join()

        total_time = time.perf_counter() - start_time
        exit_code = summarize_and_validate(total_time)
        sys.exit(exit_code)
    except threading.BrokenBarrierError:
        logger.error("并发启动超时，测试终止")
        sys.exit(1)

if __name__ == "__main__":
    main()
