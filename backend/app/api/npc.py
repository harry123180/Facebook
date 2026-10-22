"""NPC 角色管理 API。"""

from __future__ import annotations

import secrets

from flask import Blueprint, current_app, jsonify, request
from sqlalchemy import select

from ..extensions import db
from ..models import NpcProfile, User
from ..serializers import author_to_dict
from ..services import npc_service
from ..utils import (
    ApiError,
    hash_password,
    login_required,
    validate_email,
    validate_username,
)

npc_bp = Blueprint("npc", __name__, url_prefix="/api")

# 可選的 opencode 模型（後端也可以接受使用者傳入其他 provider/model）
SUGGESTED_MODELS = [
    "ollama/qwen36-nothink",
    "ollama/qwen3-coder-opencode",
    "ollama/gemma3:27b",
    "ollama/llama3:8b",
    "tsic-5090-ollama/qwen36-35b-a3b-q4km:latest",
]


@npc_bp.route("/npc", methods=["GET"])
@login_required
def list_npcs():
    profiles = db.session.execute(select(NpcProfile)).scalars().all()
    items = []
    for p in profiles:
        user = db.session.get(User, p.user_id)
        if user is None:
            continue
        items.append(
            {
                **author_to_dict(user),
                "bio": user.bio,
                "persona": p.persona,
                "model": p.model,
                "has_session": p.session_id is not None,
            }
        )
    return jsonify({"npcs": items, "suggested_models": SUGGESTED_MODELS})


@npc_bp.route("/npc", methods=["POST"])
@login_required
def create_npc():
    """建立一個 NPC 角色。

    NPC 同時是一個真的 users 資料列（所以能收發訊息、被加好友、產生通知），
    只是多了一份 persona 與 opencode session 的對應。
    """
    data = request.get_json(silent=True) or {}

    username = validate_username(data.get("username"))
    display_name = str(data.get("display_name") or "").strip() or username
    persona = str(data.get("persona") or "").strip()
    model = str(data.get("model") or "ollama/qwen36-nothink").strip()
    bio = str(data.get("bio") or "").strip() or None
    email = str(data.get("email") or f"{username}@npc.local").strip().lower()

    if not persona:
        raise ApiError("請提供角色設定（persona）", 400, "missing_persona")
    if len(persona) > 4000:
        raise ApiError("角色設定最多 4000 字元", 400, "persona_too_long")
    if not model or "/" not in model:
        raise ApiError("模型格式應為 provider/model", 400, "invalid_model")

    validate_email(email)

    exists = db.session.execute(
        select(User).where((User.username == username) | (User.email == email))
    ).scalars().first()
    if exists is not None:
        raise ApiError("這個使用者名稱或信箱已被使用", 409, "conflict")

    user = User(
        email=email,
        username=username,
        display_name=display_name,
        # NPC 不走密碼登入，給一個無法猜到的隨機雜湊
        password_hash=hash_password(secrets.token_urlsafe(32)),
        bio=bio,
        is_verified=True,
    )
    db.session.add(user)
    db.session.flush()

    db.session.add(NpcProfile(user_id=user.id, persona=persona, model=model))
    db.session.commit()

    # 背景預熱 opencode session，讓第一次聊天不用等 session 建立
    npc_service.spawn_warmup(current_app._get_current_object(), user.id)

    return (
        jsonify(
            {
                "npc": {
                    **author_to_dict(user),
                    "bio": user.bio,
                    "persona": persona,
                    "model": model,
                    "has_session": False,
                }
            }
        ),
        201,
    )


@npc_bp.route("/npc/<int:user_id>", methods=["DELETE"])
@login_required
def delete_npc(user_id: int):
    user = db.session.get(User, user_id)
    if user is None:
        raise ApiError("找不到這個 NPC", 404, "not_found")
    if db.session.get(NpcProfile, user_id) is None:
        raise ApiError("這不是一個 NPC 角色", 400, "not_npc")

    db.session.delete(user)
    db.session.commit()
    return "", 204
