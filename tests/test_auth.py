# tests/test_auth.py
import pytest
from fastapi.testclient import TestClient
from main_api import app
from utils.config import get_redis_client

client = TestClient(app)

def test_send_sms_code():
    # 清理 Redis 中的测试数据
    redis_client = get_redis_client()
    key = "sms_code:login:13800138000"
    block_key = f"{key}:block"
    redis_client.delete(key)
    redis_client.delete(block_key)

    # 发送验证码
    resp = client.post("/auth/sms/send", json={"phone_number": "13800138000"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True

    # 验证 Redis 中存在验证码
    code = redis_client.get(key)
    assert code is not None
    assert len(code) == 6

    # 验证冷却时间存在
    assert redis_client.exists(block_key)

    # 使用验证码登录
    login_resp = client.post("/auth/login/sms", json={
        "phone_number": "13800138000",
        "code": code,
        "scene": "login"
    })
    assert login_resp.status_code == 200
    login_data = login_resp.json()
    assert login_data["success"] is True
    assert "token" in login_data["data"]

    # 验证验证码已被删除
    assert redis_client.get(key) is None