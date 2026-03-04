# init_root.py
from services.auth_service import register_by_password
from services.inventory_service import get_db_session
from sqlalchemy import update
from models.user import User

def create_root():
    # 注册一个普通用户（手机号可自定义）
    result = register_by_password("13612598426", "123456", "Root Admin")
    if result["success"]:
        user_id = result["data"]["user_id"]
        with get_db_session() as session:
            session.execute(
                update(User).where(User.id == user_id).values(role='root')
            )
            session.commit()
        print("✅ root 管理员创建成功")
    else:
        print("❌ 创建失败:", result["message"])

if __name__ == "__main__":
    create_root()