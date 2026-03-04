# api/auth_routes.py

from fastapi import APIRouter, Request, HTTPException, Depends, Header
from pydantic import BaseModel
from typing import Optional

from services.auth_service import (
    register_by_password,
    login_by_password,
    get_auth_token,
    login_with_token,
    verify_phone,
    verify_token,
    send_sms_verify_code,      # 发送短信验证码
    verify_code_and_login,      # 验证码登录
)

router = APIRouter(prefix="/auth", tags=["认证"])


# ---------- 依赖项 ----------
async def get_current_user(authorization: Optional[str] = Header(None)):
    """从 Authorization 头提取 Bearer Token 并验证"""
    if not authorization:
        raise HTTPException(status_code=401, detail="未提供 Authorization 头")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer":
        raise HTTPException(status_code=401, detail="Authorization 格式错误，需使用 Bearer")
    user = verify_token(token)
    if not user:
        raise HTTPException(status_code=401, detail="Token 无效或已过期")
    return user


# ---------- 请求模型 ----------
class PasswordRegisterRequest(BaseModel):
    phone_number: str
    password: str
    nickname: Optional[str] = None

class PasswordLoginRequest(BaseModel):
    phone_number: str
    password: str

class TokenLoginRequest(BaseModel):
    verify_token: str

class PhoneVerifyRequest(BaseModel):
    phone_number: str
    sp_token: str

class SmsCodeRequest(BaseModel):
    phone_number: str
    scene: str = "login"  # 默认场景

class SmsLoginRequest(BaseModel):
    phone_number: str
    code: str
    scene: str = "login"


# ---------- 账号密码登录 ----------
@router.post("/register/password")
async def register_password(request: PasswordRegisterRequest):
    """账号密码注册"""
    result = register_by_password(
        request.phone_number,
        request.password,
        request.nickname
    )
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
    return result

@router.post("/login/password")
async def login_password(request: PasswordLoginRequest, req: Request):
    """账号密码登录"""
    client_ip = req.client.host
    result = login_by_password(
        request.phone_number,
        request.password,
        client_ip
    )
    if not result["success"]:
        raise HTTPException(status_code=401, detail=result["message"])
    return result


# ---------- 号码认证（一键登录/本机校验）----------
@router.get("/token")
async def api_get_auth_token():
    """获取前端SDK鉴权所需的 AccessToken 和 JwtToken"""
    return get_auth_token()

@router.post("/login/token")
async def api_login_with_token(request: TokenLoginRequest):
    """一键登录：用 token 换取真实手机号并登录"""
    result = login_with_token(request.verify_token)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
    return result

@router.post("/verify")
async def api_verify_phone(request: PhoneVerifyRequest):
    """本机号码校验：验证输入的手机号是否为本机号码"""
    result = verify_phone(request.phone_number, request.sp_token)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
    return result


# ---------- 短信验证码登录（降级方案）----------
@router.post("/sms/send")
async def send_sms(request: SmsCodeRequest):
    """发送短信验证码（使用阿里云测试签名）"""
    result = send_sms_verify_code(request.phone_number, request.scene)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
    return result

@router.post("/login/sms")
async def login_sms(request: SmsLoginRequest, req: Request):
    """短信验证码登录（自动注册）"""
    client_ip = req.client.host
    result = verify_code_and_login(request.phone_number, request.code, request.scene, client_ip)
    if not result["success"]:
        raise HTTPException(status_code=401, detail=result["message"])
    return result


# ---------- 受保护的用户信息接口 ----------
@router.get("/profile")
async def get_profile(user: dict = Depends(get_current_user)):
    """获取当前用户信息（需要登录）"""
    return {"user": user}