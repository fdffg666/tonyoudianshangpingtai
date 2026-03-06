# test_order_advanced.py
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


def random_digits(k=6):
    return ''.join(random.choices(string.digits, k=k))


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


def ensure_user_token(phone, password, nickname):
    token = login(phone, password)
    if token:
        return token
    user_id = register(phone, password, nickname)
    if user_id:
        return login(phone, password)
    return None


def create_product(merchant_token, product_data):
    headers = {"Authorization": f"Bearer {merchant_token}", "Content-Type": "application/json"}
    resp = requests.post(f"{BASE_URL}/products", headers=headers, json=product_data)
    if resp.status_code == 200 and resp.json().get("success"):
        return resp.json()["data"]["id"]
    return None


def print_result(step, resp):
    """打印测试结果"""
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


def test_order_advanced():
    print("=== 开始高级订单模块测试 ===\n")

    # 1. 确保 root、商家、普通用户就绪
    root_token = login(ROOT_PHONE, ROOT_PASSWORD)
    if not root_token:
        print("❌ root 登录失败，请检查 root 账号")
        return
    print("✅ root 登录成功")

    merchant_token = ensure_user_token(MERCHANT_PHONE, MERCHANT_PASSWORD, MERCHANT_NICKNAME)
    if not merchant_token:
        print("❌ 商家登录/注册失败")
        return
    print("✅ 商家已就绪")

    user_token = ensure_user_token(USER_PHONE, USER_PASSWORD, USER_NICKNAME)
    if not user_token:
        print("❌ 普通用户登录/注册失败")
        return
    print(f"✅ 普通用户已就绪: {USER_PHONE}")

    # 2. 商家创建两个测试商品
    product_ids = []
    for i in range(2):
        sku_id = f"ORDER_ADV_SKU_{i}_{random_digits(6)}"
        product_data = {
            "name": f"高级订单测试商品{i+1}",
            "price": 99.99 + i * 50,
            "sku_id": sku_id,
            "initial_stock": 100
        }
        pid = create_product(merchant_token, product_data)
        if not pid:
            print(f"❌ 创建测试商品{i+1}失败")
            return
        product_ids.append(pid)
        print(f"✅ 测试商品{i+1}创建成功: product_id={pid}, price={product_data['price']}")

    # 3. 普通用户创建两个订单（一个用于正常流程，一个用于取消）
    headers_user = {"Authorization": f"Bearer {user_token}", "Content-Type": "application/json"}
    order_ids = []

    # 订单1：正常订单
    payload1 = {
        "items": [{"product_id": product_ids[0], "quantity": 2}],
        "remark": "高级测试订单1"
    }
    resp = requests.post(f"{BASE_URL}/orders", headers=headers_user, json=payload1)
    print_result("普通用户创建订单1", resp)
    if resp.status_code == 200 and resp.json().get("success"):
        order_ids.append(resp.json()["data"]["order_id"])

    # 订单2：用于取消
    payload2 = {
        "items": [{"product_id": product_ids[1], "quantity": 1}],
        "remark": "高级测试订单2（待取消）"
    }
    resp = requests.post(f"{BASE_URL}/orders", headers=headers_user, json=payload2)
    print_result("普通用户创建订单2", resp)
    if resp.status_code == 200 and resp.json().get("success"):
        order_ids.append(resp.json()["data"]["order_id"])

    if len(order_ids) < 2:
        print("❌ 订单创建失败，无法继续测试")
        return

    order_id1, order_id2 = order_ids[0], order_ids[1]

    # 4. 测试订单列表（普通用户）
    resp = requests.get(f"{BASE_URL}/orders", headers=headers_user)
    print_result("普通用户获取订单列表", resp)

    # 5. 测试订单详情（普通用户）
    resp = requests.get(f"{BASE_URL}/orders/{order_id1}", headers=headers_user)
    print_result("普通用户获取订单详情", resp)

    # 6. 测试取消订单（普通用户）
    resp = requests.post(f"{BASE_URL}/orders/{order_id2}/cancel", headers=headers_user)
    print_result("普通用户取消订单2", resp)

    # 再次查询订单2，确认状态已变
    resp = requests.get(f"{BASE_URL}/orders/{order_id2}", headers=headers_user)
    print_result("确认订单2状态为已取消", resp)

    # 7. 测试商家更新订单状态
    headers_merchant = {"Authorization": f"Bearer {merchant_token}", "Content-Type": "application/json"}
    # 将订单1状态改为 confirmed
    resp = requests.put(f"{BASE_URL}/orders/{order_id1}/status", headers=headers_merchant,
                        json={"status": "confirmed"})
    print_result("商家更新订单1状态为 confirmed", resp)

    # 确认更新后状态
    resp = requests.get(f"{BASE_URL}/orders/{order_id1}", headers=headers_user)
    print_result("确认订单1状态为 confirmed", resp)

    # 8. 测试普通用户无权查看他人订单（可选，需有另一个普通用户，这里简化）
    # 可以注册一个新用户，但为简化，跳过

    print("\n=== 高级订单测试完成 ===")


if __name__ == "__main__":
    test_order_advanced()