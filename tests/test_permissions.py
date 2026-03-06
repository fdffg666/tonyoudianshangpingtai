# test_permissions.py
import requests
import json
import random
import string
import time

BASE_URL = "http://localhost:8000"

# 测试用户数据（请根据实际情况修改）
ROOT_PHONE = "13612598426"          # 已有的 root 账号
ROOT_PASSWORD = "123456"

MERCHANT_PHONE = "13800138001"       # 商家手机号（将被创建）
MERCHANT_PASSWORD = "merchant123"
MERCHANT_NICKNAME = "测试商家"

USER_PHONE = "13900139001"           # 普通用户手机号（将被创建）
USER_PASSWORD = "user123"
USER_NICKNAME = "测试用户"


def login(phone, password):
    """登录并返回 token，失败返回 None"""
    resp = requests.post(f"{BASE_URL}/auth/login/password",
                         json={"phone_number": phone, "password": password})
    if resp.status_code == 200 and resp.json().get("success"):
        return resp.json()["data"]["token"]
    return None


def register(phone, password, nickname):
    """注册普通用户，返回 user_id 或 None"""
    resp = requests.post(f"{BASE_URL}/auth/register/password",
                         json={"phone_number": phone, "password": password, "nickname": nickname})
    if resp.status_code == 200 and resp.json().get("success"):
        return resp.json()["data"]["user_id"]
    return None


def create_merchant_by_root(root_token, phone, password, nickname):
    """root 创建商家"""
    headers = {"Authorization": f"Bearer {root_token}", "Content-Type": "application/json"}
    resp = requests.post(f"{BASE_URL}/admin/merchants", headers=headers,
                         json={"phone_number": phone, "password": password, "nickname": nickname})
    return resp.status_code == 200 and resp.json().get("success")


def print_result(step, success, data=None, error=None):
    """格式化输出测试结果"""
    icon = "✅" if success else "❌"
    print(f"{icon} {step}")
    if data:
        print(f"   返回数据: {json.dumps(data, ensure_ascii=False, indent=2)}")
    if error:
        print(f"   错误: {error}")
    print("-" * 60)


def test_permissions():
    print("=== 开始多角色权限测试 ===\n")

    # 1. 确保 root 账号可用
    root_token = login(ROOT_PHONE, ROOT_PASSWORD)
    if not root_token:
        print("❌ root 登录失败，请检查 root 账号")
        return
    print("✅ root 登录成功")

    # 2. 创建商家账号（如果已存在则直接使用）
    merchant_token = login(MERCHANT_PHONE, MERCHANT_PASSWORD)
    if not merchant_token:
        # 用 root 创建商家
        if create_merchant_by_root(root_token, MERCHANT_PHONE, MERCHANT_PASSWORD, MERCHANT_NICKNAME):
            print(f"✅ 商家创建成功: {MERCHANT_PHONE}")
            merchant_token = login(MERCHANT_PHONE, MERCHANT_PASSWORD)
        else:
            print(f"❌ 商家创建失败，可能已存在？尝试手动登录")
            return
    else:
        print(f"✅ 商家已存在，可直接登录")

    # 3. 创建普通用户（如果不存在）
    user_token = login(USER_PHONE, USER_PASSWORD)
    if not user_token:
        user_id = register(USER_PHONE, USER_PASSWORD, USER_NICKNAME)
        if user_id:
            print(f"✅ 普通用户创建成功: {USER_PHONE}")
            user_token = login(USER_PHONE, USER_PASSWORD)
        else:
            print(f"❌ 普通用户创建失败")
            return
    else:
        print(f"✅ 普通用户已存在")

    # 准备测试商品数据
    sku_id = "SKU_TEST_" + ''.join(random.choices(string.digits, k=8))
    product_data = {
        "name": "权限测试商品",
        "price": 99.99,
        "description": "用于测试权限",
        "sku_id": sku_id,
        "initial_stock": 10
    }

    # 4. 权限测试：商品创建
    headers_user = {"Authorization": f"Bearer {user_token}", "Content-Type": "application/json"}
    headers_merchant = {"Authorization": f"Bearer {merchant_token}", "Content-Type": "application/json"}

    # 4.1 普通用户创建商品（应返回403）
    resp = requests.post(f"{BASE_URL}/products", headers=headers_user, json=product_data)
    print_result("普通用户创建商品（预期403）", resp.status_code == 403, error=resp.text)

    # 4.2 商家创建商品（应成功）
    resp = requests.post(f"{BASE_URL}/products", headers=headers_merchant, json=product_data)
    success = (resp.status_code == 200 and resp.json().get("success"))
    product_id = resp.json()["data"]["id"] if success else None
    print_result("商家创建商品（预期成功）", success, resp.json() if success else None)

    if product_id:
        # 4.3 普通用户更新商品（应403）
        update_data = {"name": "普通用户试图更新"}
        resp = requests.put(f"{BASE_URL}/products/{product_id}", headers=headers_user, json=update_data)
        print_result("普通用户更新商品（预期403）", resp.status_code == 403, error=resp.text)

        # 4.4 商家更新商品（应成功）
        update_data = {"name": "商家更新后的商品"}
        resp = requests.put(f"{BASE_URL}/products/{product_id}", headers=headers_merchant, json=update_data)
        print_result("商家更新商品（预期成功）", resp.status_code == 200 and resp.json().get("success"))

        # 4.5 普通用户删除商品（应403）
        resp = requests.delete(f"{BASE_URL}/products/{product_id}", headers=headers_user)
        print_result("普通用户删除商品（预期403）", resp.status_code == 403, error=resp.text)

        # 4.6 商家删除商品（应成功）
        resp = requests.delete(f"{BASE_URL}/products/{product_id}", headers=headers_merchant)
        print_result("商家删除商品（预期成功）", resp.status_code == 200 and resp.json().get("success"))

    # 5. root 管理商家权限测试
    headers_root = {"Authorization": f"Bearer {root_token}"}

    # 5.1 root 获取商家列表（应成功）
    resp = requests.get(f"{BASE_URL}/admin/merchants", headers=headers_root)
    print_result("root 获取商家列表", resp.status_code == 200 and resp.json().get("success"),
                 resp.json().get("data") if resp.status_code == 200 else None)

    # 5.2 商家获取商家列表（应403）
    resp = requests.get(f"{BASE_URL}/admin/merchants", headers=headers_merchant)
    print_result("商家获取商家列表（预期403）", resp.status_code == 403, error=resp.text)

    # 5.3 root 禁用商家
    # 先获取商家 ID
    merchants = requests.get(f"{BASE_URL}/admin/merchants", headers=headers_root).json().get("data", [])
    merchant_id = next((m["id"] for m in merchants if m["phone"] == MERCHANT_PHONE), None)
    if merchant_id:
        # 禁用
        resp = requests.put(f"{BASE_URL}/admin/merchants/{merchant_id}/status",
                            headers=headers_root, json={"status": 0})
        print_result("root 禁用商家", resp.status_code == 200 and resp.json().get("success"))

        time.sleep(1)  # 等待数据库更新

        # 商家尝试登录（应失败，401）
        resp = requests.post(f"{BASE_URL}/auth/login/password",
                             json={"phone_number": MERCHANT_PHONE, "password": MERCHANT_PASSWORD})
        print_result("禁用商家登录（预期401）", resp.status_code == 401, error=resp.text)

        # 启用商家
        resp = requests.put(f"{BASE_URL}/admin/merchants/{merchant_id}/status",
                            headers=headers_root, json={"status": 1})
        print_result("root 启用商家", resp.status_code == 200 and resp.json().get("success"))

        # 商家再次登录（应成功）
        resp = requests.post(f"{BASE_URL}/auth/login/password",
                             json={"phone_number": MERCHANT_PHONE, "password": MERCHANT_PASSWORD})
        print_result("启用后商家登录（预期200）", resp.status_code == 200,
                     resp.json() if resp.status_code == 200 else None)
    else:
        print("❌ 未找到商家记录，跳过禁用测试")

    print("\n=== 权限测试完成 ===")


if __name__ == "__main__":
    test_permissions()