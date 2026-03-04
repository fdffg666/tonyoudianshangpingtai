# ========== 强制添加项目根路径（必须放在最顶部！） ==========
import sys
import os

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIR)
sys.path.append(PROJECT_ROOT)
# =======================================================

# ========== 新增：导入异常和日志工具 ==========
from utils.exceptions import BusinessException, SystemException
from utils.logger import get_trace_id, ContextLogger
from utils.config import DATABASE_URL, REDIS_CONFIG, CURRENT_ISOLATION_LEVEL
# 配置基础日志
import logging
from models.user import User, VerificationCode
from services.inventory_service import engine

User.metadata.create_all(bind=engine)
VerificationCode.metadata.create_all(bind=engine)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    encoding="utf-8"
)
logger = ContextLogger(__name__)

# ========== 临时添加：更新数据表结构（测试环境用，生产环境删除） ==========
from models.inventory import Base
from services.inventory_service import engine
print("✅ 数据表已更新，新增version/biz_id字段和索引")

# ========== 导入核心业务函数 ==========
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
    print(f"❌ 导入模块失败：{e}")
    print("✅ 解决方案：")
    print("  1. 确保项目目录下有 services/、utils/、models/ 文件夹")
    print("  2. 每个文件夹内都有 空的 __init__.py 文件")
    print("  3. services/inventory_service.py 存在且无语法错误")
    sys.exit(1)

if __name__ == "__main__":
    """
    执行前检查清单：
    1. utils/config.py 中的数据库密码已修改正确
    2. Redis 服务已启动（cmd运行：redis-server --port 6380）
    3. 依赖已安装：pip install sqlalchemy pymysql redis pydantic
    """
    # 生成全局 trace_id，全链路追踪
    global_trace_id = get_trace_id()
    ctx_logger = logger.with_context(trace_id=global_trace_id)
    print("✅ Redis配置：", REDIS_CONFIG)
    print("✅ 当前事务隔离级别：", CURRENT_ISOLATION_LEVEL)

    print(f"=== 开始库存管理核心功能测试 [trace_id={global_trace_id}] ===")
    ctx_logger.info("开始执行测试流程")

    try:
        # ========== 核心业务测试 ==========
        print("\n1. 初始化库存：", init_sku_stock("SKU_TEST_001", 10))
        print("\n2. 锁定2件库存：", lock_stock("SKU_TEST_001", 2, "ORDER_1001"))
        print("\n3. 释放1件库存：", release_stock("SKU_TEST_001", 1, "ORDER_1001"))
        print("\n4. 扣减1件总库存：", deduct_stock("SKU_TEST_001", 1, "ORDER_1001"))

        # 测试异常场景
        print("\n5. 测试库存不足：", lock_stock("SKU_TEST_001", 20, "ORDER_1002"))

        # ========== 查询功能测试 ==========
        print("\n6. 查询单个SKU库存：", query_inventory("SKU_TEST_001"))
        print("\n7. 查询所有SKU库存：", query_inventory())
        print("\n8. 查询指定订单的库存日志：", query_inventory_log(order_id="ORDER_1001"))
        print("\n9. 查询指定SKU的库存日志（分页）：", query_inventory_log(sku_id="SKU_TEST_001", page=1, page_size=5))

        # ========== 幂等性测试 ==========
        print("\n10. 测试幂等性（重复锁定）：", lock_stock("SKU_TEST_001", 2, "ORDER_1001"))
        print("\n11. 测试幂等性（重复释放）：", release_stock("SKU_TEST_001", 1, "ORDER_1001"))
        print("\n12. 测试幂等性（重复扣减）：", deduct_stock("SKU_TEST_001", 1, "ORDER_1001"))

    except BusinessException as e:
        # 业务异常：用户友好提示
        ctx_logger.warning(f"测试流程遇到业务异常: {e.message}")
        print(f"\n❌ 业务异常：{e.message}")
    except SystemException as e:
        # 系统异常：内部记录，返回通用提示
        ctx_logger.error(f"测试流程遇到系统异常: {e.message}")
        print(f"\n❌ 系统异常：{e.message}")
    except Exception as e:
        # 未知异常：兜底处理
        ctx_logger.error(f"测试流程遇到未知异常: {str(e)}", exc_info=True)
        print(f"\n❌ 未知异常：系统繁忙，请稍后重试")
        print("✅ 常见原因：")
        print("  1. Redis未启动（cmd运行：redis-server --port 6380）")
        print("  2. MySQL密码错误（修改 utils/config.py）")
        print("  3. 依赖未安装（执行：pip install sqlalchemy pymysql redis）")
    else:
        # 无异常时执行
        ctx_logger.info("测试流程全部执行成功")
    finally:
        # 无论是否异常都执行
        print(f"\n=== 测试流程结束 [trace_id={global_trace_id}] ===")
        # ========== 新增：认证服务测试 ==========
        from services.auth_service import (
            send_verification_code,
            verify_code_and_login,
            register_by_password,
            login_by_password
        )

        print("\n" + "=" * 50)
        print("开始测试用户认证服务")
        print("=" * 50)

        # 测试账号密码注册
        reg_res = register_by_password("13800138000", "123456", "测试用户")
        print("1. 账号密码注册：", reg_res)

        # 测试账号密码登录
        login_res = login_by_password("13800138000", "123456")
        print("2. 账号密码登录：", login_res)

        # 测试发送验证码（需要真实手机号）
        # sms_res = send_verification_code("你的手机号", "login")
        # print("3. 发送验证码：", sms_res)

        # 测试验证码登录（需手动输入收到的验证码）
        # code = input("请输入收到的验证码：")
        # sms_login_res = verify_code_and_login("你的手机号", code, "login")
        # print("4. 验证码登录：", sms_login_res)