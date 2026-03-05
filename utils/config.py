# utils/config.py
import os
from dotenv import load_dotenv

# 加载 .env 文件（如果没有.env，用默认值）
load_dotenv()

# ===================== 基础配置 =====================
# MySQL 配置
MYSQL_USER = os.getenv("MYSQL_USER", "root")  # 补充：MySQL用户名（默认root）
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "123456")  # 替换为你的默认密码
MYSQL_HOST = os.getenv("MYSQL_HOST", "localhost")  # 补充：MySQL主机
MYSQL_PORT = os.getenv("MYSQL_PORT", "3306")  # 补充：MySQL端口
MYSQL_DB = os.getenv("MYSQL_DB", "inventory_db")  # 补充：数据库名
# 拼接数据库连接字符串（规范化）
DATABASE_URL = (
    f"mysql+pymysql://{MYSQL_USER}:{MYSQL_PASSWORD}"
    f"@{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DB}?charset=utf8mb4"
)
# 核心配置（替换为你的MySQL用户名和密码）
DB_CONFIG = {
    "host": os.getenv("MYSQL_HOST", "127.0.0.1"),
    "port": int(os.getenv("MYSQL_PORT", 3306)),
    "user": os.getenv("MYSQL_USER"),
    "password": os.getenv("MYSQL_PASSWORD"),
    "database": os.getenv("MYSQL_DB", "inventory_db"),
}
# Redis 完整配置（便于其他模块直接导入）
REDIS_CONFIG = {
    "host": os.getenv("REDIS_HOST", "localhost"),
    "port": int(os.getenv("REDIS_PORT", 6379)),
    "db": int(os.getenv("REDIS_DB", 0)),
    "decode_responses": True,  # 补充：自动解码为字符串（避免bytes类型）
    "socket_timeout": 5,  # 补充：连接超时时间（秒）
}
REDIS_LOCK_EX = int(os.getenv("REDIS_LOCK_EX", 10))  # Redis锁过期时间（秒）

# MySQL 事务隔离级别配置（用于压测对比）
MYSQL_ISOLATION_LEVEL = {
    "REPEATABLE_READ": "REPEATABLE READ",  # 原配置（幻读防护强，并发稍慢）
    "READ_COMMITTED": "READ COMMITTED"     # （并发快，幻读防护弱）
}
# 当前使用的隔离级别（先设为READ COMMITTED用于压测对比）
CURRENT_ISOLATION_LEVEL = MYSQL_ISOLATION_LEVEL["READ_COMMITTED"]

# ===================== 日志配置（补充） =====================
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")  # 日志级别：DEBUG/INFO/WARNING/ERROR
LOG_FILE = os.getenv("LOG_FILE", "app.log")  # 日志文件路径（默认当前目录app.log）
REDIS_HOST = REDIS_CONFIG["host"]
REDIS_PORT = REDIS_CONFIG["port"]
REDIS_DB = REDIS_CONFIG["db"]

# ===================== MQ 配置（核心修复：只保留一份 + 补齐broker_url） =====================
MQ_CONFIG = {
    # 核心修复：补齐broker_url（Celery必需，基于你的Redis配置）
    "broker_url": f"redis://{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}",
    # 保留你原有所有MQ配置
    "order_timeout_topic": "mq:order_timeout",  # 订单超时补偿主题
    "pay_callback_fail_topic": "mq:pay_callback_fail",  # 支付回调失败补偿主题
    "retry_max_times": 3,  # 补偿重试最大次数
    "order_timeout_seconds": 1800  # 订单超时时间（30分钟）
}
# ===================== 阿里云号码认证配置 =====================
ALIYUN_ACCESS_KEY_ID = os.getenv("ALIYUN_ACCESS_KEY_ID", "")
ALIYUN_ACCESS_KEY_SECRET = os.getenv("ALIYUN_ACCESS_KEY_SECRET", "")

# JWT配置（用于生成登录令牌）
JWT_SECRET = os.getenv("JWT_SECRET", "your-secret-key-change-in-production")
JWT_EXPIRE_HOURS = int(os.getenv("JWT_EXPIRE_HOURS", 24))  # 令牌有效期
# ===================== 微信支付配置 =====================
# TODO: 以下配置需要根据实际微信支付商户平台信息填写
WECHATPAY_MCHID = os.getenv("WECHATPAY_MCHID", "")  # 商户号
WECHATPAY_APPID = os.getenv("WECHATPAY_APPID", "")  # 应用ID（公众号/小程序/APP）
WECHATPAY_APIV3_KEY = os.getenv("WECHATPAY_APIV3_KEY", "")  # APIv3密钥（32位）
WECHATPAY_CERT_SERIAL_NO = os.getenv("WECHATPAY_CERT_SERIAL_NO", "")  # 商户证书序列号
WECHATPAY_PRIVATE_KEY_PATH = os.getenv("WECHATPAY_PRIVATE_KEY_PATH", "./certs/apiclient_key.pem")  # 商户私钥文件路径
WECHATPAY_NOTIFY_URL = os.getenv("WECHATPAY_NOTIFY_URL", "https://yourdomain.com/api/payments/notify")  # # TODO: 回调通知URL（需公网可访问）
WECHATPAY_CERT_DIR = os.getenv("WECHATPAY_CERT_DIR", "./certs")  # 平台证书缓存目录
WECHATPAY_PARTNER_MODE = os.getenv("WECHATPAY_PARTNER_MODE", "false").lower() == "true"  # 是否为服务商模式