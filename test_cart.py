# test_cart.py
import requests
import json
import random
import string
import time

BASE_URL = "http://localhost:8000"

# 测试用户数据（请确保这些账号在数据库中可用或可注册）
# root 账号（用于创建商家和商品）
ROOT_PHONE = "13612598426"       # 你的 root 手机号
ROOT_PASSWORD = "123456"

# 商家账号（用于创建测试商品）
MERCHANT_PHONE = "13800138001"
MERCHANT_PASSWORD = "merchant123"
MERCHANT_NICKNAME = "测试商家"

# 普通用户账号（购物车操作的主体）
USER_PHONE = "13900139001"
USER_PASSWORD = "user123"
USER_NICKNAME = "购物车测试用户"


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


def create_product(merchant_token, product_data):
    """商家创建商品，返回 product_id 或 None"""
    headers = {"Authorization": f"Bearer {merchant_token}", "Content-Type": "application/json"}
    resp = requests.post(f"{BASE_URL}/products", headers=headers, json=product_data)
    if resp.status_code == 200 and resp.json().get("success"):
        return resp.json()["data"]["id"]
    return None


def print_result(step, success, data=None, error=None):
    """格式化输出测试结果"""
    icon = "✅" if success else "❌"
    print(f"{icon} {step}")
    if data:
        print(f"   返回数据: {json.dumps(data, ensure_ascii=False, indent=2)}")
    if error:
        print(f"   错误: {error}")
    print("-" * 60)


def ensure_user_token(phone, password, nickname):
    """确保用户存在并返回 token（登录或注册）"""
    token = login(phone, password)
    if token:
        return token
    # 尝试注册
    user_id = register(phone, password, nickname)
    if user_id:
        return login(phone, password)
    return None


def test_cart():
    print("=== 开始购物车模块测试 ===\n")

    # 1. 确保 root 可用
    root_token = login(ROOT_PHONE, ROOT_PASSWORD)
    if not root_token:
        print("❌ root 登录失败，请检查 root 账号")
        return
    print("✅ root 登录成功")

    # 2. 确保商家存在（创建或登录）
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

    # 3. 使用商家账号创建一个测试商品
    sku_id = "CART_TEST_SKU_" + ''.join(random.choices(string.digits, k=8))
    product_data = {
        "name": "购物车测试商品",
        "price": 99.99,
        "description": "用于测试购物车功能的商品",
        "sku_id": sku_id,
        "initial_stock": 100
    }
    product_id = create_product(merchant_token, product_data)
    if not product_id:
        print("❌ 创建测试商品失败")
        return
    print(f"✅ 测试商品创建成功: product_id={product_id}")

    # 4. 确保普通用户存在并获取 token
    user_token = ensure_user_token(USER_PHONE, USER_PASSWORD, USER_NICKNAME)
    if not user_token:
        print("❌ 普通用户登录/注册失败")
        return
    print(f"✅ 普通用户已就绪: {USER_PHONE}")

    # 5. 测试购物车功能
    headers_user = {"Authorization": f"Bearer {user_token}", "Content-Type": "application/json"}

    # 5.1 添加商品到购物车
    add_payload = {"product_id": product_id, "quantity": 2}
    resp = requests.post(f"{BASE_URL}/cart/items", headers=headers_user, json=add_payload)
    print_result("添加商品到购物车", resp.status_code == 200 and resp.json().get("success"),
                 resp.json() if resp.status_code == 200 else None)

    # 5.2 查询购物车
    resp = requests.get(f"{BASE_URL}/cart", headers=headers_user)
    cart_data = None
    if resp.status_code == 200 and resp.json().get("success"):
        cart_data = resp.json()["data"]
        # 验证商品数量是否正确
        items = cart_data.get("items", [])
        found = any(item["product_id"] == product_id and item["quantity"] == 2 for item in items)
        print_result("查询购物车", found, cart_data)
    else:
        print_result("查询购物车", False, error=resp.text)

    # 5.3 更新商品数量（增加为3）
    if cart_data and cart_data["items"]:
        item_id = cart_data["items"][0]["item_id"]
        update_payload = {"quantity": 3}
        resp = requests.put(f"{BASE_URL}/cart/items/{item_id}", headers=headers_user, json=update_payload)
        print_result("更新商品数量为3", resp.status_code == 200 and resp.json().get("success"),
                     resp.json() if resp.status_code == 200 else None)

        # 再次查询确认
        resp = requests.get(f"{BASE_URL}/cart", headers=headers_user)
        if resp.status_code == 200:
            data = resp.json()
            new_qty = data["data"]["items"][0]["quantity"] if data["data"]["items"] else 0
            print_result("确认数量已更新", new_qty == 3, {"new_quantity": new_qty})
        else:
            print_result("确认数量更新失败", False, error=resp.text)

        # 5.4 将数量设为0（相当于删除）
        update_payload = {"quantity": 0}
        resp = requests.put(f"{BASE_URL}/cart/items/{item_id}", headers=headers_user, json=update_payload)
        print_result("将数量设为0（删除）", resp.status_code == 200 and resp.json().get("success"),
                     resp.json() if resp.status_code == 200 else None)

        # 确认删除后购物车为空
        resp = requests.get(f"{BASE_URL}/cart", headers=headers_user)
        if resp.status_code == 200:
            is_empty = len(resp.json()["data"]["items"]) == 0
            print_result("确认购物车已空", is_empty)
        else:
            print_result("确认购物车状态失败", False, error=resp.text)
    else:
        print("⚠️ 购物车无商品，跳过更新和删除测试")

    # 5.5 重新添加两个商品（用于测试清空）
    add_payload = {"product_id": product_id, "quantity": 1}
    resp = requests.post(f"{BASE_URL}/cart/items", headers=headers_user, json=add_payload)
    add_payload = {"product_id": product_id, "quantity": 2}
    resp = requests.post(f"{BASE_URL}/cart/items", headers=headers_user, json=add_payload)  # 累加为3
    print_result("重新添加商品（用于清空测试）", resp.status_code == 200, resp.json() if resp.status_code == 200 else None)

    # 5.6 清空购物车
    resp = requests.delete(f"{BASE_URL}/cart", headers=headers_user)
    print_result("清空购物车", resp.status_code == 200 and resp.json().get("success"),
                 resp.json() if resp.status_code == 200 else None)

    # 最终确认购物车为空
    resp = requests.get(f"{BASE_URL}/cart", headers=headers_user)
    if resp.status_code == 200:
        final_empty = len(resp.json()["data"]["items"]) == 0
        print_result("最终确认购物车为空", final_empty)
    else:
        print_result("最终确认失败", False, error=resp.text)

    print("\n=== 购物车测试完成 ===")


if __name__ == "__main__":
    test_cart()