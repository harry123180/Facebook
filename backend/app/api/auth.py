"""身份驗證 API。"""
from __future__ import annotations

from flask import Blueprint, current_app, jsonify, request

from ..extensions import db
from ..models import User
from ..services.resend_service import EmailSendError, send_verification_code, send_welcome
from ..services.verification import create_code, verify_code, VerificationError
from ..utils import (
    ApiError,
    hash_password,
    login_user,
    logout_user,
    validate_email,
    validate_password,
    validate_username,
    verify_password,
)

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")


@auth_bp.route("/register", methods=["POST"])
def register():
    """使用者註冊。"""
    try:
        data = request.get_json()
        if not data:
            raise ApiError("請提供 JSON 資料", 400, "bad_request")

        email = validate_email(data.get("email"))
        username = validate_username(data.get("username"))
        display_name = (data.get("display_name") or "").strip() or username
        password = validate_password(data.get("password"))

        # 檢查是否已存在
        existing_user = db.session.execute(
            db.select(User).where(User.email == email)
        ).scalar_one_or_none()
        if existing_user:
            raise ApiError("此信箱已被使用", 409, "conflict")

        existing_user = db.session.execute(
            db.select(User).where(User.username == username)
        ).scalar_one_or_none()
        if existing_user:
            raise ApiError("使用者名稱已被使用", 409, "conflict")

        # 建立使用者
        user = User(
            email=email,
            username=username,
            display_name=display_name,
            password_hash=hash_password(password),
        )
        db.session.add(user)
        db.session.flush()  # 獲取新用戶的ID

        try:
            # 產生驗證碼並寄信
            result = create_code(
                db, user,
                ttl_seconds=current_app.config["VERIFY_CODE_TTL_SECONDS"],
                resend_cooldown=current_app.config["VERIFY_CODE_RESEND_COOLDOWN_SECONDS"],
            )
            
            try:
                mail = send_verification_code(
                    to=email,
                    display_name=display_name,
                    code=result.code
                )
            except EmailSendError as exc:
                # 寄信失敗，回滾並報錯
                db.session.delete(user)
                db.session.commit()
                raise ApiError("寄信失敗，請稍後再試", 502, "email_send_failed") from exc

        except VerificationError:
            # 驗證碼產生失敗或冷卻中，回滾並報錯
            db.session.delete(user)
            db.session.commit()
            raise

        db.session.commit()

        payload = {
            "message": "註冊成功，請檢查信箱以取得驗證碼",
            "email": email,
            "requires_verification": True,
        }
        # 降級成 console（EMAIL_BACKEND=console 或 Resend testing mode 擋下收件人）
        # 時才回傳驗證碼，正式環境絕不洩漏
        if mail.mode == "console":
            payload["dev_code"] = result.code
            payload["delivery"] = "console"
            payload["message"] = "註冊成功。這個信箱暫時收不到信，驗證碼直接顯示給你。"
        else:
            payload["delivery"] = "resend"
        return jsonify(payload), 201

    except ApiError:
        db.session.rollback()
        raise
    except Exception:
        db.session.rollback()
        raise


@auth_bp.route("/resend-code", methods=["POST"])
def resend_code():
    """重新發送驗證碼。"""
    try:
        data = request.get_json()
        if not data:
            raise ApiError("請提供 JSON 資料", 400, "bad_request")

        email = validate_email(data.get("email"))

        # 找到用戶
        user = db.session.execute(
            db.select(User).where(User.email == email)
        ).scalar_one_or_none()
        if not user:
            raise ApiError("信箱未註冊", 404, "not_found")

        if user.is_verified:
            raise ApiError("信箱已驗證過", 400, "conflict")

        # 產生新驗證碼
        try:
            result = create_code(
                db, user,
                ttl_seconds=current_app.config["VERIFY_CODE_TTL_SECONDS"],
                resend_cooldown=current_app.config["VERIFY_CODE_RESEND_COOLDOWN_SECONDS"],
            )
        except VerificationError as exc:
            raise ApiError(exc.args[0], 429, "cooldown") from exc

        try:
            send_verification_code(
                to=email,
                display_name=user.display_name,
                code=result.code
            )
        except EmailSendError as exc:
            raise ApiError("寄信失敗，請稍後再試", 502, "email_send_failed") from exc

        return jsonify({"message": "驗證碼已重新發送"}), 200

    except ApiError:
        db.session.rollback()
        raise
    except Exception:
        db.session.rollback()
        raise


@auth_bp.route("/verify", methods=["POST"])
def verify():
    """驗證信箱。"""
    try:
        data = request.get_json()
        if not data:
            raise ApiError("請提供 JSON 資料", 400, "bad_request")

        email = validate_email(data.get("email"))
        code = data.get("code", "").strip()

        # 找到用戶
        user = db.session.execute(
            db.select(User).where(User.email == email)
        ).scalar_one_or_none()
        if not user:
            raise ApiError("信箱未註冊", 404, "not_found")

        if user.is_verified:
            return jsonify({"message": "信箱已驗證", "user": user.to_dict(include_email=True)}), 200

        # 驗證碼核對
        verified_user = verify_code(
            db, user, code, max_attempts=current_app.config["VERIFY_CODE_MAX_ATTEMPTS"]
        )

        try:
            send_welcome(
                to=email,
                display_name=verified_user.display_name
            )
        except EmailSendError:
            # 發送歡迎信失敗不影響驗證結果，但日誌記錄
            pass

        login_user(verified_user)
        db.session.commit()

        return jsonify({
            "message": "信箱驗證成功",
            "user": verified_user.to_dict(include_email=True)
        }), 200

    except VerificationError as e:
        db.session.rollback()
        raise ApiError(e.args[0], 400, "invalid_code")
    except ApiError:
        db.session.rollback()
        raise
    except Exception:
        db.session.rollback()
        raise


@auth_bp.route("/login", methods=["POST"])
def login():
    """使用者登入。"""
    try:
        data = request.get_json()
        if not data:
            raise ApiError("請提供 JSON 資料", 400, "bad_request")

        email = validate_email(data.get("email"))
        password = data.get("password", "")

        # 找到用戶
        user = db.session.execute(
            db.select(User).where(User.email == email)
        ).scalar_one_or_none()
        if not user:
            raise ApiError("信箱或密碼錯誤", 400, "invalid_credentials")

        if not user.is_verified:
            raise ApiError("請先完成信箱驗證", 403, "email_not_verified")

        # 驗證密碼
        if not user.password_hash or not password:
            raise ApiError("信箱或密碼錯誤", 400, "invalid_credentials")

        if not verify_password(user.password_hash, password):
            raise ApiError("信箱或密碼錯誤", 400, "invalid_credentials")

        # 登入用戶
        login_user(user)
        db.session.commit()

        return jsonify({
            "message": "登入成功",
            "user": user.to_dict(include_email=True)
        }), 200

    except ApiError:
        db.session.rollback()
        raise
    except Exception:
        db.session.rollback()
        raise


@auth_bp.route("/logout", methods=["POST"])
def logout():
    """使用者登出。"""
    try:
        logout_user()
        db.session.commit()
        return jsonify({"message": "已登出"}), 200
    except Exception:
        db.session.rollback()
        raise


@auth_bp.route("/me", methods=["GET"])
def me():
    """取得目前登入者資訊。"""
    from ..utils import current_user

    user = current_user()
    if not user:
        raise ApiError("請先登入", 401, "unauthorized")

    return jsonify({"user": user.to_dict(include_email=True)}), 200