# test_order_debug.py
import requests
import json
import random
import string
from datetime import datetime, timedelta

BASE_URL = "http://localhost:8000"

# 测试用户数据（请确保这些账号在数据库中可用或可注册）
ROOT_PHONE = "13612598426"
ROOT_PASSWORD = "123456"
MERCHANT_PHONE = "13800138001"
MERCHANT_PASSWORD = "merchant123"
MERCHANT_NICKNAME = "测试商家"
USER_PHONE = "13900139001"
USER_PASSWORD = "user123"
USER_NICKNAME = "订单测试用户"


def login(phone, password):
    resp = requests.post(f"{BASE_URL}/auth/login/password",
                         json={"phone_number": phone, "password": password})
    if resp.status_code == 200 and resp.json().get("success"):
        return resp.json()["data"]["token"]
    return None


def register(phone, password, nickname):
    resp = requests.post(f"{BASE_URL}/auth/register/password",
                         json={"phone_number": phone, "password": password, "nickname": nickname})
    if resp.status_code == 200 and resp.json().get("success"):
        return resp.json()["data"]["user_id"]
    return None


def create_merchant_by_root(root_token, phone, password, nickname):
    headers = {"Authorization": f"Bearer {root_token}", "Content-Type": "application/json"}
    resp = requests.post(f"{BASE_URL}/admin/merchants", headers=headers,
                         json={"phone_number": phone, "password": password, "nickname": nickname})
    return resp.status_code == 200 and resp.json().get("success")


def create_product(merchant_token, product_data):
    headers = {"Authorization": f"Bearer {merchant_token}", "Content-Type": "application/json"}
    resp = requests.post(f"{BASE_URL}/products", headers=headers, json=product_data)
    if resp.status_code == 200 and resp.json().get("success"):
        return resp.json()["data"]["id"]
    return None


def ensure_user_token(phone, password, nickname):
    token = login(phone, password)
    if token:
        return token
    user_id = register(phone, password, nickname)
    if user_id:
        return login(phone, password)
    return None


def print_result(step, resp):
    """增强版打印函数，自动处理响应"""
    if resp.status_code == 200:
        data = resp.json()
        if data.get("success"):
            icon = "✅"
            print(f"{icon} {step}")
            print(f"   返回数据: {json.dumps(data['data'], ensure_ascii=False, indent=2)}")
        else:
            icon = "❌"
            print(f"{icon} {step}（业务失败）")
            print(f"   错误信息: {data.get('message')}")
    else:
        icon = "❌"
        print(f"{icon} {step}（HTTP {resp.status_code}）")
        try:
            error_detail = resp.json()
            print(f"   错误: {json.dumps(error_detail, ensure_ascii=False)}")
        except:
            print(f"   错误: {resp.text}")
    print("-" * 60)


def test_order():
    print("=== 开始订单模块测试 ===\n")

    root_token = login(ROOT_PHONE, ROOT_PASSWORD)
    if not root_token:
        print("❌ root 登录失败，请检查 root 账号")
        return
    print("✅ root 登录成功")

    merchant_token = login(MERCHANT_PHONE, MERCHANT_PASSWORD)
    if not merchant_token:
        if create_merchant_by_root(root_token, MERCHANT_PHONE, MERCHANT_PASSWORD, MERCHANT_NICKNAME):
            print("✅ 商家创建成功")
            merchant_token = login(MERCHANT_PHONE, MERCHANT_PASSWORD)
        else:
            print("❌ 商家创建失败")
            return
    else:
        print("✅ 商家已存在，直接登录")

    product_ids = []
    for i in range(2):
        sku_id = f"ORDER_TEST_SKU_{i}_{''.join(random.choices(string.digits, k=6))}"
        product_data = {
            "name": f"订单测试商品{i+1}",
            "price": 99.99 + i * 50,
            "description": f"用于测试订单的商品{i+1}",
            "sku_id": sku_id,
            "initial_stock": 100
        }
        pid = create_product(merchant_token, product_data)
        if not pid:
            print(f"❌ 创建测试商品{i+1}失败")
            return
        product_ids.append(pid)
        print(f"✅ 测试商品{i+1}创建成功: product_id={pid}, price={product_data['price']}")

    user_token = ensure_user_token(USER_PHONE, USER_PASSWORD, USER_NICKNAME)
    if not user_token:
        print("❌ 普通用户登录/注册失败")
        return
    print(f"✅ 普通用户已就绪: {USER_PHONE}")

    headers_user = {"Authorization": f"Bearer {user_token}", "Content-Type": "application/json"}

    # 5.1 正常创建订单
    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    order_items = [
        {"product_id": product_ids[0], "quantity": 2},
        {"product_id": product_ids[1], "quantity": 3}
    ]
    payload = {
        "items": order_items,
        "expected_delivery_date": tomorrow,
        "remark": "测试订单，请及时处理"
    }
    resp = requests.post(f"{BASE_URL}/orders", headers=headers_user, json=payload)
    print_result("创建订单（正常）", resp)

    # 5.2 商品列表为空
    payload = {"items": []}
    resp = requests.post(f"{BASE_URL}/orders", headers=headers_user, json=payload)
    print_result("创建订单（空商品列表）", resp)

    # 5.3 商品数量为0
    payload = {"items": [{"product_id": product_ids[0], "quantity": 0}]}
    resp = requests.post(f"{BASE_URL}/orders", headers=headers_user, json=payload)
    print_result("创建订单（数量为0）", resp)

    # 5.4 商品不存在
    payload = {"items": [{"product_id": 999999, "quantity": 1}]}
    resp = requests.post(f"{BASE_URL}/orders", headers=headers_user, json=payload)
    print_result("创建订单（商品不存在）", resp)

    # 5.5 日期格式错误
    payload = {
        "items": [{"product_id": product_ids[0], "quantity": 1}],
        "expected_delivery_date": "2026-13-01"
    }
    resp = requests.post(f"{BASE_URL}/orders", headers=headers_user, json=payload)
    print_result("创建订单（日期格式错误）", resp)

    # 5.6 未提供 token
    resp = requests.post(f"{BASE_URL}/orders", json=payload)
    print_result("创建订单（未登录）", resp)

    # 5.7 商家创建订单
    headers_merchant = {"Authorization": f"Bearer {merchant_token}", "Content-Type": "application/json"}
    payload = {"items": [{"product_id": product_ids[0], "quantity": 1}]}
    resp = requests.post(f"{BASE_URL}/orders", headers=headers_merchant, json=payload)
    print_result("商家创建订单", resp)

    print("\n=== 订单测试完成 ===")


if __name__ == "__main__":
    test_order()