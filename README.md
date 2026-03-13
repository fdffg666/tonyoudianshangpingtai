# 钨钢刀具电商平台后端系统

## 项目简介
这是一个基于 FastAPI 开发的电商后台系统，专为钨钢刀具等工业品的小工厂采购场景设计。系统实现了从用户认证、商品管理、库存控制、购物车、订单处理到微信支付的全流程，并采用分布式锁、乐观锁、幂等性设计等机制确保高并发下的数据一致性。

## 功能特性

### 1. 库存管理
- **初始化/重置库存**：为 SKU 设置初始库存，支持幂等和强制重置。
- **库存锁定**：下单时锁定商品库存，防止超卖。
- **库存释放**：订单取消或超时后解锁库存。
- **库存扣减**：支付成功后永久扣减总库存。
- **操作日志**：记录每次变更前后的库存快照，支持分页查询。
- **定时对账**：每天凌晨自动核对库存与日志，发现异常及时告警。

### 2. 用户认证与权限
- **账号密码注册/登录**：加盐哈希存储密码，JWT 无状态认证。
- **短信验证码登录**：集成阿里云号码认证（测试签名可用，无需申请）。
- **阿里云一键登录**：H5 端本机号码校验和一键登录。
- **角色权限**：普通用户、商家、root 管理员三级权限，通过依赖注入控制接口访问。
- **管理员功能**：root 可创建/禁用商家账号。

### 3. 商品管理
- **商品增删改查**：名称、价格、描述、图片、分类等字段。
- **自动关联库存**：创建商品时可同时初始化库存。

### 4. 购物车
- **添加/修改/删除商品**：支持同一商品累加数量，置 0 自动删除。
- **实时计算金额**：返回商品最新价格和小计。

### 5. 订单管理
- **创建订单**：从商品列表生成订单，记录价格快照，支持备注和期望交货日期。
- **订单列表/详情**：分页查询，支持状态筛选。
- **取消订单**：仅限待支付状态，可释放库存。
- **商家更新状态**：商家/root 可流转订单状态（确认、发货、完成）。

### 6. 支付集成（微信 Native 支付）
- **生成支付二维码**：调用微信统一下单接口，返回 code_url。
- **支付回调处理**：验证签名，更新支付记录和订单状态。
- **支付结果查询**：支持主动查询，结果缓存。

### 7. 消息补偿与最终一致性
- **订单超时自动释放**：通过 Redis 队列消费，调用释放库存接口。
- **支付失败重试**：支付回调失败后重试扣减库存（最多 3 次）。

### 8. 监控与日志
- **链路追踪**：每个请求生成 `trace_id`，贯穿所有日志。
- **Prometheus 指标**：预定义了锁失败、库存不足、DB 错误等计数器。

### 9. 测试套件
- **单元测试**：覆盖库存、商品、权限等模块。
- **并发压测**：模拟高并发锁定库存，验证防超卖能力。
- **权限测试**：验证不同角色的接口访问控制。

## 技术栈

- **开发语言**：Python 3.12
- **Web 框架**：FastAPI
- **ORM**：SQLAlchemy 2.0
- **数据库**：MySQL 8.0
- **缓存/锁/队列**：Redis 5.0
- **支付 SDK**：`wechatpayv3`
- **认证**：JWT + 阿里云号码认证 SDK
- **部署**：支持 Uvicorn + Gunicorn，可容器化

## 目录结构
tonyoudianshangpingtai/
├── main_api.py # FastAPI 应用入口
├── init_root.py # 初始化 root 管理员脚本
├── test_*.py # 各类测试脚本（并发、权限、订单、支付等）
├── .env # 环境变量配置（敏感信息）
├── requirements.txt # 依赖列表
├── api/ # 接口层
│ ├── auth_routes.py
│ ├── inventory_routes.py
│ ├── product_routes.py
│ ├── cart_routes.py
│ ├── order_routes.py
│ ├── payment_routes.py
│ └── admin_routes.py
├── services/ # 业务逻辑层
│ ├── auth_service.py
│ ├── inventory_service.py
│ ├── product_service.py
│ ├── cart_service.py
│ ├── order_service.py
│ └── payment_service.py
├── models/ # 数据模型层
│ ├── base.py # 统一 Base
│ ├── user.py
│ ├── product.py
│ ├── inventory.py
│ ├── cart.py
│ ├── order.py
│ ├── payment.py
│ └── message.py
├── utils/ # 工具库
│ ├── config.py
│ ├── logger.py
│ ├── exceptions.py
│ ├── redis_lock.py
│ ├── metrics.py
│ └── mq.py
└── tasks/ # 异步任务
└── message_tasks.py

## 快速开始

### 1. 环境准备
- Python 3.12+
- MySQL 8.0+
- Redis 5.0+

### 2. 克隆项目并安装依赖
```bash
git clone <你的仓库地址>
cd tonyoudianshangpingtai
pip install -r requirements.txt
```
# MySQL 配置
MYSQL_USER=root
MYSQL_PASSWORD=你的MySQL密码
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_DB=inventory_db

# Redis 配置
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0

# JWT 配置
JWT_SECRET=your-secret-key-change-in-production
JWT_EXPIRE_HOURS=24

# 阿里云号码认证（可选，如需短信验证码登录）
ALIYUN_ACCESS_KEY_ID=你的AccessKeyId
ALIYUN_ACCESS_KEY_SECRET=你的AccessKeySecret

# 微信支付配置（如需支付功能）
# TODO: 申请微信支付商户号后填写
WECHATPAY_MCHID=
WECHATPAY_APPID=
WECHATPAY_APIV3_KEY=
WECHATPAY_CERT_SERIAL_NO=
WECHATPAY_PRIVATE_KEY_PATH=./certs/apiclient_key.pem
WECHATPAY_NOTIFY_URL=https://yourdomain.com/api/payments/notify
WECHATPAY_CERT_DIR=./certs
CREATE DATABASE inventory_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
# API 文档概览
启动服务后，访问 /docs 可查看所有接口的详细文档。主要接口分类：

认证 (/auth)：注册、登录、短信验证码、一键登录、令牌刷新。

商品 (/products)：商品的增删改查。

库存 (/inventory)：库存操作（锁定、释放、扣减）及查询。

购物车 (/cart)：购物车管理。

订单 (/orders)：订单创建、列表、详情、取消、状态更新。

支付 (/payments)：支付下单、回调、查询。

管理员 (/admin)：商家管理（仅 root 可访问）。
# 常见问题
启动时提示表不存在
项目启动时会自动创建表（Base.metadata.create_all），但需确保数据库连接正确且用户有建表权限。若表未自动创建，可手动执行建表 SQL。

微信支付配置不完整
支付模块会检查配置，若缺失则返回“微信支付客户端初始化失败”。如需测试，可暂时注释支付路由或配置测试商户号。

阿里云短信验证码发送失败
确保 .env 中已配置正确的 AccessKey，且使用了官方测试签名和模板（已内置），无需申请。
