# models/user.py
from sqlalchemy import Column, Integer, String, DateTime, Boolean, Index
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime
import hashlib
import os

Base = declarative_base()


class User(Base):
    """用户表"""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    phone_number = Column(String(11), unique=True, nullable=False, index=True, comment="手机号")
    password_hash = Column(String(128), nullable=True, comment="密码哈希值（可为空，验证码登录用户无密码）")
    salt = Column(String(32), nullable=True, comment="密码盐值")
    nickname = Column(String(50), nullable=True, comment="昵称")
    avatar = Column(String(255), nullable=True, comment="头像URL")
    status = Column(Integer, default=1, comment="状态：0-禁用，1-正常")
    last_login_time = Column(DateTime, nullable=True, comment="最后登录时间")
    last_login_ip = Column(String(45), nullable=True, comment="最后登录IP")
    clast_login_ip = Column(String(45), nullable=True, comment="最后登录IP（IPv6地址最长45）")
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    __table_args__ = (
        Index("idx_phone_status", "phone_number", "status"),
    )

    def set_password(self, password: str):
        """设置密码（加盐哈希）"""
        self.salt = os.urandom(16).hex()
        self.password_hash = hashlib.sha256(
            (password + self.salt).encode()
        ).hexdigest()

    def check_password(self, password: str) -> bool:
        """验证密码"""
        if not self.password_hash or not self.salt:
            return False
        calc_hash = hashlib.sha256(
            (password + self.salt).encode()
        ).hexdigest()
        return calc_hash == self.password_hash


class VerificationCode(Base):
    """短信验证码表"""
    __tablename__ = "verification_codes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    phone_number = Column(String(11), nullable=False, index=True)
    code = Column(String(6), nullable=False)
    scene = Column(String(20), nullable=False, comment="场景：login/register/reset_password")
    is_used = Column(Boolean, default=False)
    expire_time = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.now)

    __table_args__ = (
        Index("idx_phone_scene_used", "phone_number", "scene", "is_used"),
    )