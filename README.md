# 电商库存防超卖管理系统

## 项目简介
这是一个基于 Python 开发的工业级库存管理核心模块，主要解决电商高并发场景下的「库存超卖」问题。

**核心功能：**
1.  初始化/重置商品库存
2.  下单时锁定库存
3.  取消订单时释放库存
4.  支付成功后扣减总库存
5.  双重防超卖（Redis 分布式锁 + MySQL 行级锁）

## 技术栈
- **开发语言**：Python 3.12
- **ORM 框架**：SQLAlchemy
- **数据库**：MySQL 8.0
- **缓存/锁**：Redis 5.0
- **并发控制**：数据库事务 + 分布式锁

## 目录结构
PythonProject/
├── main.py # 项目入口 / 测试脚本
├── utils/ # 工具层
│ ├── config.py # 配置文件
│ └── redis_lock.py # Redis 分布式锁
├── services/ # 业务层
│ └── inventory_service.py # 库存核心业务逻辑
└── models/ # 数据模型层
└── inventory.py # 数据库表结构定义

## 快速开始
### 1. 环境准备
确保你已经安装了：
- Python 3.10+
- MySQL 8.0+
- Redis 5.0+

### 2. 安装依赖
打开终端（Terminal），执行：
# 电商库存防超卖管理系统

## 项目简介
这是一个基于 Python 开发的工业级库存管理核心模块，主要解决电商高并发场景下的「库存超卖」问题。

**核心功能：**
1.  初始化/重置商品库存
2.  下单时锁定库存
3.  取消订单时释放库存
4.  支付成功后扣减总库存
5.  双重防超卖（Redis 分布式锁 + MySQL 行级锁）

## 技术栈
- **开发语言**：Python 3.12
- **ORM 框架**：SQLAlchemy
- **数据库**：MySQL 8.0
- **缓存/锁**：Redis 5.0
- **并发控制**：数据库事务 + 分布式锁

## 目录结构
PythonProject/
├── main.py # 项目入口 / 测试脚本
├── utils/ # 工具层
│ ├── config.py # 配置文件
│ └── redis_lock.py # Redis 分布式锁
├── services/ # 业务层
│ └── inventory_service.py # 库存核心业务逻辑
└── models/ # 数据模型层
└── inventory.py # 数据库表结构定义

## 快速开始
### 1. 环境准备
确保你已经安装了：
- Python 3.10+
- MySQL 8.0+
- Redis 5.0+

### 2. 安装依赖
打开终端（Terminal），执行：

```bash
pip install sqlalchemy pymysql redis
```
3. 修改配置
打开 utils/config.py，修改以下内容：
python
运行
```bash
# 把 "你的MySQL密码" 改成你本地 MySQL 的 root 密码
DATABASE_URL = "mysql+pymysql://root:你的MySQL密码@localhost:3306/wugang_tool_platform?charset=utf8mb4"

# 确保 Redis 端口和你启动的一致
REDIS_PORT = 6380
```
4. 启动服务
启动 Redis：打开 CMD，执行 redis-server --port 6380（保持窗口打开）；
运行项目：在 PyCharm 里右键点击 main.py，选择「Run 'main'」。
运行效果
运行 main.py 后，你会看到：
1.初始化库存成功
2.锁定库存成功
3.释放库存成功
4.扣减库存成功
5.库存不足时被正确拦截
核心亮点:
1.双重防超卖：结合 Redis 分布式锁和 MySQL 行级锁，确保高并发下库存不超卖；
2.事务控制：库存更新和日志写入在同一个事务里，保证数据一致性；
3.分层架构：配置 / 模型 / 业务 / 入口分离，代码结构清晰；
4.完整日志：记录每次库存操作前的快照，方便追溯。
## 并发压测验证
### 1. 运行压测脚本
在项目根目录运行：
```bash
python test_concurrent.py