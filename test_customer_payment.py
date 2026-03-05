# test_customer_payment.py
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
USER_NICKNAME = "客服支付测试用户"


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
        return resp.json()["data"]
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


def test_customer_payment():
    print("=== 开始客服支付模式测试 ===\n")

    # 1. 确保商家和普通用户就绪
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
    sku_id = f"CUSTOMER_PAY_SKU_{random_digits(8)}"
    product_data = {
        "name": "客服支付测试商品",
        "price": 99.99,
        "sku_id": sku_id,
        "initial_stock": 100
    }
    product_id = create_product(merchant_token, product_data)
    if not product_id:
        print("❌ 创建测试商品失败")
        return
    print(f"✅ 测试商品创建成功: product_id={product_id}")

    # 3. 普通用户创建订单
    order_items = [{"product_id": product_id, "quantity": 2}]
    order_data = create_order(user_token, order_items, remark="客服支付测试")
    if not order_data:
        print("❌ 创建订单失败")
        return
    print("✅ 订单创建成功")
    print(f"   返回数据: {json.dumps(order_data, ensure_ascii=False, indent=2)}")

    # 4. 验证返回的客服微信号
    from utils.config import CUSTOMER_WECHAT_ID
    if order_data.get("customer_wechat"):
        print(f"✅ 客服微信号返回: {order_data['customer_wechat']}")
    else:
        print("❌ 客服微信号未返回，请检查配置")
        return

    order_id = order_data["order_id"]

    # 5. 商家确认付款（应成功）
    headers_merchant = {"Authorization": f"Bearer {merchant_token}", "Content-Type": "application/json"}
    confirm_payload = {"order_id": order_id}
    resp = requests.post(f"{BASE_URL}/admin/orders/confirm-payment", headers=headers_merchant, json=confirm_payload)
    print_result("商家确认付款", resp)

    # 6. 确认订单状态已变为 confirmed
    headers_user = {"Authorization": f"Bearer {user_token}"}
    resp = requests.get(f"{BASE_URL}/orders/{order_id}", headers=headers_user)
    if resp.status_code == 200:
        data = resp.json()
        if data["data"]["status"] == "confirmed":
            print("✅ 订单状态已更新为 confirmed")
        else:
            print(f"❌ 订单状态为 {data['data']['status']}，预期 confirmed")
    else:
        print_result("查询订单状态", resp)

    # 7. 异常测试：普通用户尝试确认付款（应403）
    resp = requests.post(f"{BASE_URL}/admin/orders/confirm-payment", headers=headers_user, json=confirm_payload)
    print_result("普通用户确认付款（预期403）", resp)

    # 8. 异常测试：确认不存在的订单
    resp = requests.post(f"{BASE_URL}/admin/orders/confirm-payment", headers=headers_merchant,
                         json={"order_id": 99999})
    print_result("确认不存在的订单", resp)

    # 9. 异常测试：对已确认的订单再次确认（应返回错误）
    resp = requests.post(f"{BASE_URL}/admin/orders/confirm-payment", headers=headers_merchant, json=confirm_payload)
    print_result("重复确认同一订单（应失败）", resp)

    print("\n=== 客服支付测试完成 ===")


if __name__ == "__main__":
    test_customer_payment()