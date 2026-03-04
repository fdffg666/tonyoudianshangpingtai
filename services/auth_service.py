# services/auth_service.py
import hashlib
import jwt
import random
import string
import json
from datetime import datetime, timedelta
from typing import Dict, Optional
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from models.user import User, VerificationCode
from services.inventory_service import get_db_session, _ok, _fail
from utils.config import (
    ALIYUN_ACCESS_KEY_ID, ALIYUN_ACCESS_KEY_SECRET,
    JWT_SECRET, JWT_EXPIRE_HOURS
)
from utils.logger import ContextLogger, get_trace_id
from utils.exceptions import BusinessException

# 阿里云号码认证 SDK
from alibabacloud_dypnsapi20170525.client import Client as DypnsapiClient
from alibabacloud_tea_openapi import models as open_api_models
from alibabacloud_dypnsapi20170525 import models as dypnsapi_models
from alibabacloud_tea_util import models as util_models

logger = ContextLogger(__name__)

# 验证码缓存（生产环境请使用 Redis）
verify_code_cache = {}


def _generate_jwt_token(user_id: int, phone_number: str) -> str:
    payload = {
        "user_id": user_id,
        "phone": phone_number,
        "exp": datetime.utcnow() + timedelta(hours=JWT_EXPIRE_HOURS),
        "iat": datetime.utcnow()
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")


def _create_dypns_client() -> DypnsapiClient:
    config = open_api_models.Config(
        access_key_id=ALIYUN_ACCESS_KEY_ID,
        access_key_secret=ALIYUN_ACCESS_KEY_SECRET
    )
    config.endpoint = "dypnsapi.aliyuncs.com"
    return DypnsapiClient(config)


def generate_verify_code(length=6) -> str:
    return ''.join(random.choices(string.digits, k=length))
def register_by_password(phone_number: str, password: str, nickname: str = None) -> Dict:
    trace_id = get_trace_id()
    ctx_logger = logger.with_context(trace_id=trace_id, phone=phone_number)

    if not phone_number or not password:
        return _fail("手机号和密码不能为空")

    try:
        with get_db_session() as session:
            existing = session.execute(
                select(User).where(User.phone_number == phone_number)
            ).scalar_one_or_none()
            if existing:
                return _fail("该手机号已注册")

            user = User(
                phone_number=phone_number,
                nickname=nickname or phone_number,
                role='user'
            )
            user.set_password(password)  # 假设 User 模型有 set_password 方法
            session.add(user)
            session.commit()

            token = _generate_jwt_token(user.id, user.phone_number)
            ctx_logger.info(f"用户注册成功: id={user.id}")
            return _ok(
                "注册成功",
                {
                    "user_id": user.id,
                    "phone": user.phone_number,
                    "nickname": user.nickname,
                    "token": token,
                },
            )
    except Exception as e:
        ctx_logger.error(f"注册失败: {e}", exc_info=True)
        return _fail("注册失败，请稍后重试")


def login_by_password(login_name: str, password: str, ip: str = None) -> Dict:
    trace_id = get_trace_id()
    ctx_logger = logger.with_context(trace_id=trace_id, login_name=login_name)

    try:
        with get_db_session() as session:
            # 支持手机号或用户名登录，这里先按手机号查
            user = session.execute(
                select(User).where(User.phone_number == login_name, User.status == 1)
            ).scalar_one_or_none()
            if not user:
                return _fail("用户不存在或已被禁用")

            if not user.check_password(password):
                return _fail("密码错误")

            user.last_login_time = datetime.now()
            user.last_login_ip = ip
            session.commit()

            token = _generate_jwt_token(user.id, user.phone_number)
            ctx_logger.info(f"用户登录成功: id={user.id}")
            return _ok(
                "登录成功",
                {
                    "user_id": user.id,
                    "phone": user.phone_number,
                    "nickname": user.nickname,
                    "token": token,
                },
            )
    except Exception as e:
        ctx_logger.error(f"登录失败: {e}", exc_info=True)
        return _fail("登录失败，请稍后重试")

def get_auth_token() -> Dict:
        client = _create_dypns_client()
        request = dypnsapi_models.GetAuthTokenRequest()
        try:
            response = client.get_auth_token(request)
            if response.body.code == "OK":
                data = response.body.token_info or {}
                return _ok(
                    data={
                        "accessToken": data.access_token,
                        "jwtToken": data.jwt_token,
                    }
                )
            else:
                return _fail(f"获取鉴权Token失败: {response.body.message}")
        except Exception as e:
            logger.error(f"获取鉴权Token异常: {e}", exc_info=True)
            return _fail(f"系统异常: {str(e)}")

def login_with_token(verify_token: str) -> Dict:
        client = _create_dypns_client()
        request = dypnsapi_models.GetPhoneWithTokenRequest()
        request.token = verify_token
        try:
            response = client.get_phone_with_token(request)
            if response.body.code == "OK":
                phone_number = response.body.data.mobile
                # 登录或自动注册
                with get_db_session() as session:
                    user = session.execute(
                        select(User).where(User.phone_number == phone_number)
                    ).scalar_one_or_none()
                    if not user:
                        user = User(phone_number=phone_number, nickname=f"用户{phone_number[-4:]}")
                        session.add(user)
                        session.commit()
                        session.refresh(user)
                    token = _generate_jwt_token(user.id, user.phone_number)
                    return _ok(data={"phone": phone_number, "token": token})
            else:
                return _fail(f"换取手机号失败: {response.body.message}")
        except Exception as e:
            logger.error(f"登录换取手机号异常: {e}", exc_info=True)
            return _fail(f"系统异常: {str(e)}")

def verify_phone(phone_number: str, sp_token: str) -> Dict:
        client = _create_dypns_client()
        request = dypnsapi_models.VerifyPhoneWithTokenRequest()
        request.phone_number = phone_number
        request.sp_token = sp_token
        try:
            response = client.verify_phone_with_token(request)
            if response.body.code == "OK":
                is_verify = response.body.data.verify_result
                if is_verify:
                    return _ok(data={"is_verified": True})
                else:
                    return _fail("号码校验失败，可能不是本机号码")
            else:
                return _fail(f"校验服务异常: {response.body.message}")
        except Exception as e:
            logger.error(f"本机校验异常: {e}", exc_info=True)
            return _fail(f"系统异常: {str(e)}")
def send_sms_verify_code(phone_number: str, scene: str = "login") -> Dict:
    trace_id = get_trace_id()
    ctx_logger = logger.with_context(trace_id=trace_id, phone=phone_number, scene=scene)

    if not phone_number or not phone_number.isdigit() or len(phone_number) != 11:
        return _fail("手机号格式错误")

    cache_key = f"{phone_number}:{scene}"
    if cache_key in verify_code_cache:
        cache_info = verify_code_cache[cache_key]
        if datetime.now() < cache_info["next_send_time"]:
            remain = (cache_info["next_send_time"] - datetime.now()).seconds
            return _fail(f"请{remain}秒后再试")

    code = generate_verify_code()

    try:
        client = _create_dypns_client()
        request = dypnsapi_models.SendSmsVerifyCodeRequest(
            phone_number=phone_number,
            sign_name="速通互联验证码",          # 阿里云提供的测试签名
            template_code="100001",               # 测试模板CODE
            template_param=json.dumps({
                "code": code,            # 注意格式
                "min": "5"
            })
        )
        runtime = util_models.RuntimeOptions()
        response = client.send_sms_verify_code_with_options(request, runtime)

        if response.body.code == "OK":
            verify_code_cache[cache_key] = {
                "code": code,
                "expires_at": datetime.now() + timedelta(minutes=5),
                "next_send_time": datetime.now() + timedelta(seconds=60),
            }
            ctx_logger.info(f"验证码发送成功: {code}")
            return _ok("验证码发送成功")
        else:
            ctx_logger.error(f"发送失败: {response.body.message}")
            return _fail(f"发送失败: {response.body.message}")
    except Exception as e:
        ctx_logger.error(f"发送验证码异常: {e}", exc_info=True)
        return _fail("系统异常，请稍后重试")


def verify_code_and_login(phone_number: str, code: str, scene: str = "login", ip: str = None) -> Dict:
    trace_id = get_trace_id()
    ctx_logger = logger.with_context(trace_id=trace_id, phone=phone_number)

    cache_key = f"{phone_number}:{scene}"
    cache_info = verify_code_cache.get(cache_key)
    ctx_logger.info(f"验证码缓存: {cache_info}")  # 新增日志
    if not cache_info:
        ctx_logger.warning(f"缓存中无该手机号验证码: {cache_key}")
        return _fail("验证码未发送或已过期")
    if datetime.now() > cache_info["expires_at"]:
        ctx_logger.warning(f"验证码已过期, 过期时间: {cache_info['expires_at']}")
        del verify_code_cache[cache_key]
        return _fail("验证码已过期")
    if cache_info["code"] != code:
        ctx_logger.warning(f"验证码错误, 输入: {code}, 正确: {cache_info['code']}")
        return _fail("验证码错误")

    del verify_code_cache[cache_key]

    try:
        with get_db_session() as session:
            user = session.execute(
                select(User).where(User.phone_number == phone_number)
            ).scalar_one_or_none()
            if not user:
                user = User(phone_number=phone_number, nickname=f"用户{phone_number[-4:]}",role='user')
                session.add(user)
                session.flush()
                ctx_logger.info(f"新用户自动注册: id={user.id}")

            user.last_login_time = datetime.now()
            user.last_login_ip = ip
            session.commit()

            token = _generate_jwt_token(user.id, user.phone_number)
            return _ok(
                "登录成功",
                {
                    "user_id": user.id,
                    "phone": user.phone_number,
                    "nickname": user.nickname,
                    #"is_new": user.created_at > datetime.now() - timedelta(seconds=5),
                    "token": token,
                },
            )
    except Exception as e:
        ctx_logger.error(f"登录失败: {e}", exc_info=True)
        return _fail("登录失败，请稍后重试")

def verify_token(token: str) -> Optional[Dict]:
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        return {"user_id": payload["user_id"], "phone": payload["phone"]}
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None
