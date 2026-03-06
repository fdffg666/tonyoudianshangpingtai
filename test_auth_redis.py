import requests
import json
import time
import subprocess
import sys
import os
import redis
from utils.config import get_redis_client
BASE_URL = "http://localhost:8000"
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # 添加项目根目录到路径

# 测试手机号（请使用你自己的手机号，确保能收到短信）
TEST_PHONE = "13612598426"  # 替换为实际手机号
TEST_PASSWORD = "123456"

def print_result(step, success, data=None, error=None):
    icon = "✅" if success else "❌"
    print(f"{icon} {step}")
    if data:
        print(f"   返回数据: {json.dumps(data, ensure_ascii=False, indent=2)}")
    if error:
        print(f"   错误: {error}")
    print("-" * 60)

def test_redis_sms():
    """测试验证码 Redis 存储"""
    print("\n=== 1. 测试短信验证码 Redis 存储 ===")

    # 发送验证码
    resp = requests.post(f"{BASE_URL}/auth/sms/send", json={"phone_number": TEST_PHONE})
    if resp.status_code != 200:
        print_result("发送验证码", False, error=f"HTTP {resp.status_code}: {resp.text}")
        return False
    data = resp.json()
    if not data.get("success"):
        print_result("发送验证码", False, error=data.get("message"))
        return False
    print_result("发送验证码", True, data)

    # 检查 Redis 中是否存在验证码（需要 redis-cli）
    redis_client = get_redis_client()
    redis_key = f"sms_code:login:{TEST_PHONE}"
    code = redis_client.get(redis_key)
    if code:
        print(f"✅ Redis 中存在验证码: {code}")
        ttl = redis_client.ttl(redis_key)
        print(f"   过期时间剩余: {ttl} 秒")
        # 检查冷却标记
        block_key = f"{redis_key}:block"
        if redis_client.exists(block_key):
            block_ttl = redis_client.ttl(block_key)
            print(f"   冷却标记存在，剩余: {block_ttl} 秒")
        else:
            print("❌ 冷却标记不存在")
        return code
    else:
        print("❌ Redis 中未找到验证码")
        return None

def test_sms_login(code):
    """测试短信验证码登录"""
    print("\n=== 2. 测试短信验证码登录 ===")
    if not code:
        print("❌ 跳过登录测试，缺少验证码")
        return False
    resp = requests.post(f"{BASE_URL}/auth/login/sms", json={
        "phone_number": TEST_PHONE,
        "code": code,
        "scene": "login"
    })
    if resp.status_code != 200:
        print_result("短信登录", False, error=f"HTTP {resp.status_code}: {resp.text}")
        return False
    data = resp.json()
    if data.get("success"):
        print_result("短信登录", True, data)
        # 验证 Redis 中验证码已被删除
        redis_key = f"sms_code:login:{TEST_PHONE}"
        result = subprocess.run(
            ["redis-cli", "GET", redis_key],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0 and not result.stdout.strip():
            print("✅ 验证码已从 Redis 中删除")
        else:
            print("❌ 验证码未被删除")
        return True
    else:
        print_result("短信登录", False, error=data.get("message"))
        return False

def test_password_register():
    """测试密码注册（bcrypt 哈希）"""
    print("\n=== 3. 测试密码注册 ===")
    # 先尝试删除可能存在的用户（避免冲突）
    # 注意：此操作会真实删除数据库用户，谨慎使用。建议手动清理或使用新手机号。
    # 这里我们假设每次测试使用唯一手机号，避免清理。
    # 为简单，我们可以使用 TEST_PHONE + 时间戳
    unique_phone = f"139{int(time.time())%100000000:08d}"  # 临时生成新手机号
    print(f"使用临时手机号: {unique_phone}")
    resp = requests.post(f"{BASE_URL}/auth/register/password", json={
        "phone_number": unique_phone,
        "password": TEST_PASSWORD,
        "nickname": "测试用户"
    })
    if resp.status_code != 200:
        print_result("密码注册", False, error=f"HTTP {resp.status_code}: {resp.text}")
        return None
    data = resp.json()
    if data.get("success"):
        print_result("密码注册", True, data)
        return unique_phone
    else:
        print_result("密码注册", False, error=data.get("message"))
        return None

def test_password_login(phone, password):
    """测试密码登录并验证 bcrypt 哈希"""
    print("\n=== 4. 测试密码登录 ===")
    resp = requests.post(f"{BASE_URL}/auth/login/password", json={
        "phone_number": phone,
        "password": password
    })
    if resp.status_code != 200:
        print_result("密码登录", False, error=f"HTTP {resp.status_code}: {resp.text}")
        return False
    data = resp.json()
    if data.get("success"):
        print_result("密码登录", True, data)
        # 检查数据库中的密码哈希是否为 bcrypt
        # 需要手动查看数据库，或通过另一个接口查询（但当前没有提供）
        print("   请手动检查数据库中 password_hash 是否以 $2b$ 开头")
        return True
    else:
        print_result("密码登录", False, error=data.get("message"))
        return False

def main():
    print("=" * 60)
    print("开始综合测试：验证码 Redis 存储 + 密码哈希 bcrypt")
    print("=" * 60)

    # 测试 1: 发送验证码并检查 Redis
    code = test_redis_sms()
    if not code:
        print("❌ 验证码发送失败，退出测试")
        return

    # 等待几秒（可选）
    time.sleep(2)

    # 测试 2: 短信验证码登录
    sms_ok = test_sms_login(code)
    if not sms_ok:
        print("❌ 短信登录失败，继续测试密码部分")

    # 测试 3: 密码注册
    new_phone = test_password_register()
    if not new_phone:
        print("❌ 密码注册失败，测试终止")
        return

    # 测试 4: 密码登录
    login_ok = test_password_login(new_phone, TEST_PASSWORD)
    if not login_ok:
        print("❌ 密码登录失败")
    else:
        print("✅ 密码登录成功")

    print("\n=== 测试完成 ===")

if __name__ == "__main__":
    main()