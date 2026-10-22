"""應用程式設定。

所有設定從環境變數讀取，本機開發由專案根目錄的 .env 提供。
"""

import os
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv

# backend/app/config.py -> backend/app -> backend -> 專案根目錄
BASE_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BASE_DIR.parent

# 讓本機 .env 生效
load_dotenv(PROJECT_ROOT / ".env")


def _int_env(key: str, default: int) -> int:
    raw = os.getenv(key)
    if raw is None or raw.strip() == "":
        return default
    try:
        return int(raw)
    except ValueError:
        return default


class BaseConfig:
    """共用設定。"""

    SECRET_KEY = os.getenv("SECRET_KEY", "dev-only-insecure-key")

    # --- 資料庫 ---
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL", "postgresql+psycopg://fbapp:fbapp@127.0.0.1:5435/facebook_mvp"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,       # 避免連線被防火牆/容器重置後拿到壞連線
        "pool_recycle": 1800,
    }

    # --- Session ---
    # 單機 MVP 用 signed cookie session，不需要 Redis。
    # 內容只放 user_id，不放貼文等敏感或大物件。
    SESSION_COOKIE_NAME = "fb_session"
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"   # 同站 (tunnel 網址) 導覽時才會帶，Lax 足夠擋大部分 CSRF
    SESSION_COOKIE_SECURE = os.getenv("SESSION_COOKIE_SECURE", "auto")
    PERMANENT_SESSION_LIFETIME = timedelta(days=7)

    # --- Resend ---
    RESEND_API_KEY = os.getenv("RESEND_API_KEY", "")
    RESEND_FROM_EMAIL = os.getenv("RESEND_FROM_EMAIL", "Facebook MVP <onboarding@resend.dev>")
    RESEND_FROM_NAME = os.getenv("RESEND_FROM_NAME", "Facebook MVP")
    # EMAIL_BACKEND:
    #   "auto"    -> 嘗試真實寄信；若 Resend 因 testing mode 擋下收件人，
    #                自動降級成 console（驗證碼印 log + 回傳 dev_code），註冊流程不會壞掉
    #   "console" -> 一律不寄信，驗證碼印 log 並回傳 dev_code
    #   "resend"  -> 一律真實寄信，失敗就回 502
    # 注意：Resend 帳號在 testing mode 時只能寄到 onboarding@resend.dev 之類的
    # 測試信箱，或是帳號註冊者本人的信箱。
    EMAIL_BACKEND = os.getenv("EMAIL_BACKEND", "auto").lower()

    # --- Email 驗證碼 ---
    VERIFY_CODE_TTL_SECONDS = _int_env("VERIFY_CODE_TTL_SECONDS", 600)          # 10 分鐘
    VERIFY_CODE_RESEND_COOLDOWN_SECONDS = _int_env(
        "VERIFY_CODE_RESEND_COOLDOWN_SECONDS", 60
    )
    VERIFY_CODE_MAX_ATTEMPTS = _int_env("VERIFY_CODE_MAX_ATTEMPTS", 5)

    # --- 其他 ---
    FRONTEND_ORIGIN = os.getenv("FRONTEND_ORIGIN", "http://localhost:5173")
    MAX_CONTENT_LENGTH = 8 * 1024 * 1024   # 單檔上傳上限 8MB
    UPLOAD_FOLDER = str(BASE_DIR / "static" / "uploads")
    ALLOWED_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}
    JSON_SORT_KEYS = False
    TEMPLATES_AUTO_RELOAD = True

    # --- NPC（opencode 當 LLM 引擎）---
    NPC_TIMEOUT = _int_env("NPC_TIMEOUT", 120)   # 單次回覆逾時秒數
    NPC_WARMUP_TIMEOUT = _int_env("NPC_WARMUP_TIMEOUT", 300)  # 預熱逾時（首次載入模型較久）
    NPC_DEFAULT_MODEL = os.getenv("NPC_DEFAULT_MODEL", "ollama/qwen36-nothink")
    NPC_WARMUP = os.getenv("NPC_WARMUP", "1") == "1"   # 建立 NPC 時先預熱 session


class DevelopmentConfig(BaseConfig):
    DEBUG = True


class ProductionConfig(BaseConfig):
    DEBUG = False
    # Secure cookie 由 TunnelAwareSessionInterface 依對外協定自動判斷，
    # 需要強制時設 SESSION_COOKIE_SECURE=1
    SESSION_COOKIE_SECURE = os.getenv("SESSION_COOKIE_SECURE", "auto")


def get_config() -> type[BaseConfig]:
    env = os.getenv("FLASK_ENV", "development").lower()
    if env == "production":
        return ProductionConfig
    return DevelopmentConfig
