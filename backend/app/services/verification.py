"""Email 驗證碼的產生、雜湊與核對。

安全設計：
- 驗證碼用 secrets.choice 產生（密碼學安全亂數），不是 random。
- DB 不存明文驗證碼，只存 sha256(code + salt)。
- 同一時間只允許一筆未使用的驗證碼，重發會作廢舊的。
- 驗證失敗次數有上限，超過就作廢該碼，避免 6 位數被暴力破解（100 萬種可能）。
- 重發有冷卻時間，避免被拿來洗信箱或燒 Resend 額度。
"""

from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import EmailVerificationCode, User

CODE_LENGTH = 6


class VerificationError(Exception):
    """驗證失敗。message 是要給使用者看的說明。"""


@dataclass
class VerificationResult:
    user: User
    code: str


def generate_code() -> str:
    """產生 6 位數驗證碼（密碼學安全）。"""
    return "".join(str(secrets.randbelow(10)) for _ in range(CODE_LENGTH))


def _new_salt() -> str:
    return secrets.token_hex(16)


def hash_code(code: str, salt: str) -> str:
    return hashlib.sha256(f"{code}:{salt}".encode("utf-8")).hexdigest()


def create_code(db: Session, user: User, *, ttl_seconds: int, resend_cooldown: int) -> VerificationResult:
    """產生新驗證碼並寫入 DB。

    - 作廢該使用者所有尚未使用的舊驗證碼
    - 若上一筆驗證碼建立於冷卻時間內，拋出 VerificationError
    """
    now = datetime.now(timezone.utc)

    latest = db.session.execute(
        select(EmailVerificationCode)
        .where(EmailVerificationCode.user_id == user.id)
        .order_by(EmailVerificationCode.created_at.desc())
        .limit(1)
    ).scalar_one_or_none()

    if latest is not None and latest.used_at is None:
        created = latest.created_at
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        elapsed = (now - created).total_seconds()
        if elapsed < resend_cooldown:
            wait = int(resend_cooldown - elapsed)
            raise VerificationError(f"請 {wait} 秒後再重新取得驗證碼")

    # 作廢所有未使用的舊碼
    stale = db.session.execute(
        select(EmailVerificationCode).where(
            EmailVerificationCode.user_id == user.id,
            EmailVerificationCode.used_at.is_(None),
        )
    ).scalars().all()
    for old in stale:
        old.used_at = now

    code = generate_code()
    salt = _new_salt()
    record = EmailVerificationCode(
        user_id=user.id,
        code_hash=hash_code(code, salt),
        salt=salt,
        expires_at=now + timedelta(seconds=ttl_seconds),
        attempts=0,
    )
    db.session.add(record)
    db.session.commit()
    return VerificationResult(user=user, code=code)


def verify_code(db: Session, user: User, code: str, *, max_attempts: int) -> User:
    """核對驗證碼。成功則回傳已驗證的使用者。"""
    now = datetime.now(timezone.utc)

    record = db.session.execute(
        select(EmailVerificationCode)
        .where(EmailVerificationCode.user_id == user.id, EmailVerificationCode.used_at.is_(None))
        .order_by(EmailVerificationCode.created_at.desc())
        .limit(1)
    ).scalar_one_or_none()

    if record is None:
        raise VerificationError("沒有有效中的驗證碼，請重新取得")

    expires = record.expires_at
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    if now > expires:
        record.used_at = now
        db.session.commit()
        raise VerificationError("驗證碼已過期，請重新取得")

    if record.attempts >= max_attempts:
        record.used_at = now
        db.session.commit()
        raise VerificationError("嘗試次數過多，請重新取得驗證碼")

    record.attempts += 1

    if not secrets.compare_digest(record.code_hash, hash_code(code.strip(), record.salt)):
        db.session.commit()
        remaining = max_attempts - record.attempts
        raise VerificationError(f"驗證碼不正確，還有 {remaining} 次機會")

    record.used_at = now
    user.is_verified = True
    db.session.commit()
    return user
