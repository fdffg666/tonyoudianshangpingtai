# utils/compensate.py
import time
import threading
from utils.mq import consume_mq_msg, send_mq_msg, get_msg_len
from utils.config import MQ_CONFIG
from services.inventory_service import release_stock, deduct_stock, query_inventory, query_inventory_log
from utils.logger import ContextLogger

logger = ContextLogger(__name__)


def compensate_order_timeout():
    """补偿：处理超时未支付订单，释放锁定库存"""

    def run():
        logger.info("订单超时补偿服务已启动...")
        while True:
            try:
                msg = consume_mq_msg(MQ_CONFIG["order_timeout_topic"])
                if not msg:
                    time.sleep(1)
                    continue

                # 校验订单是否超时
                create_time = msg.get("create_time")
                current_time = int(time.time())
                if current_time - create_time < MQ_CONFIG["order_timeout_seconds"]:
                    # 未超时，重新入队
                    send_mq_msg(MQ_CONFIG["order_timeout_topic"], msg)
                    time.sleep(1)
                    continue

                # 执行库存释放
                order_id = msg.get("order_id")
                sku_id = msg.get("sku_id")
                lock_num = msg.get("lock_num")
                result = release_stock(sku_id, lock_num, order_id)
                if result["success"]:
                    logger.info(f"超时订单补偿成功: 订单{order_id}，释放SKU{sku_id}库存{lock_num}件")
                else:
                    # 补偿失败，重试（最多3次）
                    retry_times = msg.get("retry_times", 0) + 1
                    if retry_times <= MQ_CONFIG["retry_max_times"]:
                        msg["retry_times"] = retry_times
                        send_mq_msg(MQ_CONFIG["order_timeout_topic"], msg)
                        logger.warning(f"超时订单补偿失败，将重试: 订单{order_id}，重试次数{retry_times}")
                    else:
                        logger.error(f"超时订单补偿失败，已达最大重试次数: 订单{order_id}")
            except Exception as e:
                logger.error(f"订单超时补偿服务异常: {e}")
                time.sleep(5)  # 异常时暂停5秒再继续

    # 启动补偿线程
    t = threading.Thread(target=run, daemon=True)
    t.start()


def compensate_pay_callback_fail():
    """补偿：处理支付回调失败的订单，重试扣减库存"""

    def run():
        logger.info("支付回调失败补偿服务已启动...")
        while True:
            try:
                msg = consume_mq_msg(MQ_CONFIG["pay_callback_fail_topic"])
                if not msg:
                    time.sleep(1)
                    continue

                # 执行库存扣减重试
                order_id = msg.get("order_id")
                sku_id = msg.get("sku_id")
                deduct_num = msg.get("deduct_num")
                result = deduct_stock(sku_id, deduct_num, order_id)
                if result["success"]:
                    logger.info(f"支付回调补偿成功: 订单{order_id}，扣减SKU{sku_id}库存{deduct_num}件")
                else:
                    # 补偿失败，重试（最多3次）
                    retry_times = msg.get("retry_times", 0) + 1
                    if retry_times <= MQ_CONFIG["retry_max_times"]:
                        msg["retry_times"] = retry_times
                        send_mq_msg(MQ_CONFIG["pay_callback_fail_topic"], msg)
                        logger.warning(f"支付回调补偿失败，将重试: 订单{order_id}，重试次数{retry_times}")
                    else:
                        logger.error(f"支付回调补偿失败，已达最大重试次数: 订单{order_id}")
            except Exception as e:
                logger.error(f"支付回调补偿服务异常: {e}")
                time.sleep(5)

    # 启动补偿线程
    t = threading.Thread(target=run, daemon=True)
    t.start()


def reconcile_inventory():
    """定时对账：核对库存数据一致性（每天凌晨2点执行）"""

    def run():
        logger.info("库存对账服务已启动...")
        while True:
            try:
                # 检查是否到对账时间（每天凌晨2点）
                current_time = time.localtime()
                if current_time.tm_hour == 2 and current_time.tm_min == 0:
                    logger.info("开始执行库存对账...")

                    # 1. 查询所有SKU库存
                    inventory_result = query_inventory()
                    if not inventory_result["success"]:
                        logger.error(f"查询库存失败，对账终止: {inventory_result['message']}")
                        time.sleep(60)
                        continue

                    sku_list = inventory_result["data"]
                    for sku in sku_list:
                        sku_id = sku["sku_id"]
                        # 2. 查询该SKU的所有操作日志
                        log_result = query_inventory_log(sku_id=sku_id, page_size=1000)
                        if not log_result["success"]:
                            logger.error(f"查询SKU{sku_id}日志失败，跳过对账: {log_result['message']}")
                            continue

                        # 3. 根据日志计算理论库存
                        total_stock = 0
                        locked_stock = 0
                        for log in log_result["data"]["list"]:
                            if log["change_type"] == "INIT":
                                total_stock = log["change_amount"]
                            elif log["change_type"] == "LOCK":
                                locked_stock += log["change_amount"]
                            elif log["change_type"] == "RELEASE":
                                locked_stock -= log["change_amount"]
                            elif log["change_type"] == "DEDUCT":
                                total_stock -= log["change_amount"]
                                locked_stock -= log["change_amount"]

                        # 4. 对比实际库存和理论库存
                        actual_total = sku["total_stock"]
                        actual_locked = sku["locked_stock"]
                        if actual_total != total_stock or actual_locked != locked_stock:
                            logger.error(
                                f"库存对账异常: SKU{sku_id} "
                                f"实际总库存={actual_total}, 理论总库存={total_stock} "
                                f"实际锁定库存={actual_locked}, 理论锁定库存={locked_stock}"
                            )
                        else:
                            logger.info(f"库存对账正常: SKU{sku_id}")

                    logger.info("库存对账完成")
                    # 对账完成后，等待1小时再检查（避免重复执行）
                    time.sleep(3600)
                else:
                    # 未到对账时间，每分钟检查一次
                    time.sleep(60)
            except Exception as e:
                logger.error(f"库存对账服务异常: {e}")
                time.sleep(300)

    # 启动对账线程
    t = threading.Thread(target=run, daemon=True)
    t.start()


def start_all_compensate_services():
    """启动所有补偿和对账服务"""
    compensate_order_timeout()
    compensate_pay_callback_fail()
    reconcile_inventory()
    logger.info("所有补偿和对账服务已启动")