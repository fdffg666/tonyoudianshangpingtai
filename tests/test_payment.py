# test_payment.py
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
USER_NICKNAME = "支付测试用户"


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


def create_order(user_token, items, remark=None):
    headers = {"Authorization": f"Bearer {user_token}", "Content-Type": "application/json"}
    payload = {"items": items, "remark": remark}
    resp = requests.post(f"{BASE_URL}/orders", headers=headers, json=payload)
    if resp.status_code == 200 and resp.json().get("success"):
        return resp.json()["data"]["order_id"]
    return None


def print_result(step, resp):
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


def test_payment():
    print("=== 开始支付模块测试 ===\n")

    # 1. 确保用户就绪
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

    # 2. 商家创建测试商品
    sku_id = f"PAY_TEST_SKU_{random_digits(8)}"
    product_data = {
        "name": "支付测试商品",
        "price": 88.88,
        "sku_id": sku_id,
        "initial_stock": 100
    }
    product_id = create_product(merchant_token, product_data)
    if not product_id:
        print("❌ 创建测试商品失败")
        return
    print(f"✅ 测试商品创建成功: product_id={product_id}")

    # 3. 普通用户创建测试订单
    order_items = [{"product_id": product_id, "quantity": 2}]
    order_id = create_order(user_token, order_items, remark="支付测试订单")
    if not order_id:
        print("❌ 创建测试订单失败")
        return
    print(f"✅ 测试订单创建成功: order_id={order_id}")

    headers_user = {"Authorization": f"Bearer {user_token}", "Content-Type": "application/json"}

    # 4. 测试创建支付订单
    payload = {"order_id": order_id}
    resp = requests.post(f"{BASE_URL}/payments/native", headers=headers_user, json=payload)
    print_result("创建支付订单（正常）", resp)
    if resp.status_code == 200 and resp.json().get("success"):
        code_url = resp.json()["data"]["code_url"]
        print(f"   二维码链接: {code_url}")

    # 5. 测试重复创建支付订单（应返回已有的二维码）
    resp = requests.post(f"{BASE_URL}/payments/native", headers=headers_user, json=payload)
    print_result("重复创建支付订单（应返回缓存）", resp)

    # 6. 测试查询支付结果（此时应返回 NOTPAY）
    resp = requests.get(f"{BASE_URL}/payments/{order_id}", headers=headers_user)
    print_result("查询支付结果", resp)

    # 7. 测试未登录访问
    resp = requests.get(f"{BASE_URL}/payments/{order_id}")
    print_result("未登录查询支付", resp)

    # 8. 测试其他用户查询（应无权限）
    headers_merchant = {"Authorization": f"Bearer {merchant_token}"}
    resp = requests.get(f"{BASE_URL}/payments/{order_id}", headers=headers_merchant)
    print_result("商家查询他人订单（预期403）", resp)

    # 9. 测试订单不存在
    resp = requests.get(f"{BASE_URL}/payments/999999", headers=headers_user)
    print_result("查询不存在的支付", resp)

    print("\n=== 支付测试完成 ===")


if __name__ == "__main__":
    test_payment()