# ========== 强制添加项目根路径 ==========
import sys
import os
import uuid
import logging
import threading
import time
import argparse
import random
from typing import Dict, List, Tuple

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.append(PROJECT_ROOT)

from services.inventory_service import init_sku_stock, lock_stock, query_inventory, query_inventory_log

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# 全局变量（将在 main 中重新赋值）
results = []
result_lock = threading.Lock()
start_barrier = None
SKU_IDS = []          # 存储所有 SKU ID
TOTAL_STOCK_PER_SKU = 0
LOCK_NUM_PER_REQUEST = 1

def parse_args():
    parser = argparse.ArgumentParser(description="库存并发压测脚本（增强版）")
    parser.add_argument("--total", type=int, default=10000, help="总库存（平均分配到每个 SKU）")
    parser.add_argument("--skus", type=int, default=10, help="SKU 数量（分散锁竞争）")
    parser.add_argument("--concurrent", type=int, default=500, help="并发线程数")
    parser.add_argument("--lock-num", type=int, default=1, help="每次锁定数量")
    parser.add_argument("--redis-lock", action="store_true", help="启用Redis锁（默认关闭）")
    return parser.parse_args()

def init_all_skus(base_sku_id: str, total_stock: int, sku_count: int):
    """初始化多个 SKU，每个分配均等库存"""
    global SKU_IDS, TOTAL_STOCK_PER_SKU
    per_sku = total_stock // sku_count
    remainder = total_stock % sku_count
    SKU_IDS = []
    for i in range(sku_count):
        sku = f"{base_sku_id}_{i}"
        stock = per_sku + (1 if i < remainder else 0)  # 余数分配到前几个 SKU
        result = init_sku_stock(sku, stock, force=True)
        if not result.get("success"):
            logger.error(f"初始化 SKU {sku} 失败：{result.get('message')}")
            return False
        SKU_IDS.append(sku)
    TOTAL_STOCK_PER_SKU = per_sku
    logger.info(f"初始化 {sku_count} 个 SKU 完成，每个约 {per_sku} 件")
    return True

def concurrent_lock_task(order_id: str, args):
    """每个线程的任务：随机选择一个 SKU，锁定并执行一次读操作"""
    try:
        start_barrier.wait()
        sku_id = random.choice(SKU_IDS)  # 随机 SKU 分散竞争

        # 读操作（触发快照读 / 当前读，取决于隔离级别）
        # 此处查询日志，不影响库存，但会增加事务时间并暴露隔离级别差异
        log_result = query_inventory_log(sku_id=sku_id, page_size=1)

        start_time = time.perf_counter()
        result = lock_stock(sku_id, LOCK_NUM_PER_REQUEST, order_id)
        elapsed = time.perf_counter() - start_time
        result["elapsed_ms"] = elapsed * 1000
        result["sku_id"] = sku_id  # 记录操作的 SKU
    except threading.BrokenBarrierError:
        return
    except Exception as e:
        result = {"success": False, "message": f"线程异常: {str(e)}", "elapsed_ms": 0, "sku_id": "unknown"}
        logger.error(f"任务执行异常: {e}", exc_info=True)

    with result_lock:
        results.append({
            "order_id": order_id,
            "sku_id": result.get("sku_id"),
            "success": bool(result.get("success")),
            "message": result.get("message", ""),
            "elapsed_ms": result.get("elapsed_ms", 0)
        })

def summarize_and_validate(total_time: float, args) -> int:
    success_items = [r for r in results if r["success"]]
    fail_items = [r for r in results if not r["success"]]
    success_count = len(success_items)
    fail_count = len(fail_items)

    # 统计版本冲突次数
    version_conflicts = sum(1 for r in fail_items if "版本冲突" in r["message"])
    other_fails = fail_count - version_conflicts

    # 查询所有 SKU 的最终库存并求和
    total_actual = 0
    total_locked = 0
    for sku in SKU_IDS:
        inv = query_inventory(sku)
        if inv.get("success"):
            data = inv["data"]
            total_actual += data["total_stock"]
            total_locked += data["locked_stock"]

    logger.info("\n=== 压测结果汇总 ===")
    logger.info(f"测试参数：总库存={args.total}, SKU数={args.skus}, 并发数={args.concurrent}, 单次锁定={args.lock_num}")
    logger.info(f"Redis锁：{'启用' if args.redis_lock else '关闭'}")
    logger.info(f"总耗时：{total_time:.4f} 秒 (TPS: {args.concurrent / total_time:.2f})")
    logger.info(f"总请求数：{args.concurrent} 个")
    logger.info(f"成功锁定：{success_count} 个")
    logger.info(f"失败拦截：{fail_count} 个")
    logger.info(f"  ├─ 版本冲突：{version_conflicts} 个")
    logger.info(f"  └─ 其他失败：{other_fails} 个")
    logger.info(f"最终库存总和：{total_actual} 件")
    logger.info(f"最终锁定总和：{total_locked} 件")

    # 核心校验
    checks = []
    checks.append(("请求总数一致", success_count + fail_count == args.concurrent))
    max_possible_success = args.total // args.lock_num
    checks.append(("未发生超卖", success_count <= max_possible_success))

    # 允许的错误类型
    allowed_errors = ["库存不足", "系统繁忙", "获取分布式锁失败", "版本冲突"]
    abnormal_fail = [r for r in fail_items if not any(err in r["message"] for err in allowed_errors)]
    checks.append(("无异常报错", len(abnormal_fail) == 0))

    # 数据守恒
    expected_locked_total = success_count * args.lock_num
    checks.append(("总库存不变", total_actual == args.total))
    checks.append(("锁定总数正确", total_locked == success_count * args.lock_num))

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
            logger.error(f"- {item['order_id']} (SKU={item['sku_id']}): {item['message']}")

    return 0 if all_passed else 1

def main():
    args = parse_args()
    RUN_ID = uuid.uuid4().hex[:8]
    base_sku = f"SKU_TEST_{RUN_ID}"

    global start_barrier, LOCK_NUM_PER_REQUEST
    start_barrier = threading.Barrier(args.concurrent + 1)
    LOCK_NUM_PER_REQUEST = args.lock_num

    # 在应用层设置 Redis 锁开关（通过环境变量或直接修改配置，此处假设已在代码中控制）
    # 为了不影响其他测试，可以在脚本中临时修改配置，但复杂，建议通过 args.redis_lock 在业务层判断
    # 这里我们只做压测，不修改代码，需提前在 inventory_service.py 中根据环境变量控制 ENABLE_REDIS_LOCK
    # 简单起见，我们假设 args.redis_lock 已正确反映

    logger.info("=== 库存防超卖并发压测开始 ===")
    logger.info(f"测试配置：总库存={args.total}件 | SKU数={args.skus} | 并发数={args.concurrent} | 单次锁定={args.lock_num}")

    # 初始化多个 SKU
    if not init_all_skus(base_sku, args.total, args.skus):
        sys.exit(1)

    # 启动线程
    threads = []
    for i in range(args.concurrent):
        order_id = f"TEST_ORDER_{RUN_ID}_{i+1}"
        t = threading.Thread(target=concurrent_lock_task, args=(order_id, args))
        threads.append(t)
        t.start()

    logger.info("2. 线程准备就绪，开始并发...")

    try:
        start_time = time.perf_counter()
        start_barrier.wait(timeout=30)
        for t in threads:
            t.join()
        total_time = time.perf_counter() - start_time
        exit_code = summarize_and_validate(total_time, args)
        sys.exit(exit_code)
    except threading.BrokenBarrierError:
        logger.error("并发启动超时，测试终止")
        sys.exit(1)

if __name__ == "__main__":
    main()