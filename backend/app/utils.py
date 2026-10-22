"""共用工具：認證、錯誤回應、輸入驗證。"""

from __future__ import annotations

import re
from functools import wraps
from typing import Any, Callable

from flask import jsonify, session
from werkzeug.security import check_password_hash, generate_password_hash

from .extensions import db
from .models import User

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
USERNAME_RE = re.compile(r"^[A-Za-z0-9_]{3,30}$")


class ApiError(Exception):
    """帶 HTTP 狀態碼與機器可讀 code 的 API 錯誤。"""

    def __init__(self, message: str, status: int = 400, code: str = "bad_request", **extra: Any):
        super().__init__(message)
        self.message = message
        self.status = status
        self.code = code
        self.extra = extra


def hash_password(raw: str) -> str:
    """scrypt（Werkzeug 3.x 預設），比 PBKDF2 更抗 GPU 爆破。"""
    return generate_password_hash(raw, method="scrypt")


def verify_password(hashed: str, raw: str) -> bool:
    try:
        return check_password_hash(hashed, raw)
    except (ValueError, TypeError):
        return False


def validate_email(email: str) -> str:
    email = (email or "").strip().lower()
    if not email or len(email) > 255 or not EMAIL_RE.match(email):
        raise ApiError("請輸入有效的電子郵件", 400, "invalid_email")
    return email


def validate_username(username: str) -> str:
    username = (username or "").strip()
    if not USERNAME_RE.match(username):
        raise ApiError("使用者名稱需為 3-30 個英數字或底線", 400, "invalid_username")
    return username


def validate_password(password: str) -> str:
    if not password or len(password) < 8:
        raise ApiError("密碼至少需要 8 個字元", 400, "weak_password")
    if len(password) > 128:
        raise ApiError("密碼長度過長", 400, "weak_password")
    return password


# --------------------------------------------------------------------------
# 認證
# --------------------------------------------------------------------------
def current_user() -> User | None:
    """從 session 取得目前登入者。"""
    user_id = session.get("user_id")
    if not user_id:
        return None
    user = db.session.get(User, user_id)
    if user is None:
        session.clear()
        return None
    return user


def login_required(fn: Callable) -> Callable:
    @wraps(fn)
    def wrapper(*args, **kwargs):
        user = current_user()
        if user is None:
            raise ApiError("請先登入", 401, "unauthorized")
        if not user.is_verified:
            raise ApiError("請先完成信箱驗證", 403, "email_not_verified")
        return fn(*args, **kwargs)

    return wrapper


def login_user(user: User) -> None:
    session.clear()
    session["user_id"] = user.id
    session.permanent = True


def logout_user() -> None:
    session.clear()


# --------------------------------------------------------------------------
# 分頁
# --------------------------------------------------------------------------
def pagination_args(default_limit: int = 20, max_limit: int = 50) -> tuple[int, int]:
    """從 query string 取 offset/limit，並夾在合理範圍內。"""
    from flask import request

    try:
        page = max(int(request.args.get("page", 1)), 1)
    except (TypeError, ValueError):
        page = 1
    try:
        limit = int(request.args.get("limit", default_limit))
    except (TypeError, ValueError):
        limit = default_limit
    limit = max(1, min(limit, max_limit))
    return (page - 1) * limit, limit
