from services.inventory_service import engine
from sqlalchemy import text  # 必须导入 text

print("=== 数据库隔离级别验证 ===")

with engine.connect() as conn:
    # 核心修改：用 text() 包装 SQL 字符串，兼容 SQLAlchemy 2.0
    result_session = conn.execute(text("SELECT @@session.transaction_isolation;"))
    session_isolation = result_session.scalar()

    result_global = conn.execute(text("SELECT @@global.transaction_isolation;"))
    global_isolation = result_global.scalar()

    print(f"当前会话隔离级别：{session_isolation}")
    print(f"全局默认隔离级别：{global_isolation}")

if session_isolation == "READ-COMMITTED":
    print("\n✅ RC隔离级别已完全生效，压测数据会准确体现RC的性能优势")
else:
    print("\n❌ 隔离级别未生效，请检查engine配置")