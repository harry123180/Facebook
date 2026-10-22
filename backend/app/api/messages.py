"""私人訊息 API。

MVP 用短輪詢（前端每 3 秒）而不是 WebSocket：
Quick Tunnel 對 WebSocket 的支援較脆弱，輪詢取穩定優先。
"""

from __future__ import annotations

from datetime import datetime, timezone

from flask import Blueprint, current_app, jsonify, request
from sqlalchemy import select

from ..extensions import db
from ..models import (
    Conversation,
    ConversationMember,
    Message,
    Notification,
    User,
)
from ..serializers import conversation_to_dict, message_to_dict
from ..services import npc_service
from ..utils import ApiError, current_user, login_required

messages_bp = Blueprint("messages", __name__, url_prefix="/api")


def _is_member(conversation_id: int, user_id: int) -> bool:
    return db.session.execute(
        select(ConversationMember).where(
            ConversationMember.conversation_id == conversation_id,
            ConversationMember.user_id == user_id,
        )
    ).scalar_one_or_none() is not None


def _find_direct_conversation(user_a: int, user_b: int) -> Conversation | None:
    """找兩個使用者之間既有的 1:1 對話（沒有就回 None）。"""
    convs = db.session.execute(
        select(Conversation)
        .join(ConversationMember, ConversationMember.conversation_id == Conversation.id)
        .where(ConversationMember.user_id == user_a)
    ).scalars().all()

    for conv in convs:
        members = db.session.execute(
            select(ConversationMember.user_id).where(
                ConversationMember.conversation_id == conv.id
            )
        ).scalars().all()
        if len(members) == 2 and user_b in members:
            return conv
    return None


@messages_bp.route("/messages/conversations", methods=["GET"])
@login_required
def list_conversations():
    me = current_user()
    convs = db.session.execute(
        select(Conversation)
        .join(ConversationMember, ConversationMember.conversation_id == Conversation.id)
        .where(ConversationMember.user_id == me.id)
        .order_by(
            Conversation.last_message_at.desc().nullslast(),
            Conversation.id.desc(),
        )
    ).scalars().all()

    return jsonify(
        {"conversations": [conversation_to_dict(c, me.id) for c in convs]}
    )


@messages_bp.route("/messages/conversations", methods=["POST"])
@login_required
def create_conversation():
    me = current_user()
    data = request.get_json(silent=True) or {}

    try:
        other_id = int(data.get("user_id"))
    except (TypeError, ValueError):
        raise ApiError("請提供有效的 user_id", 400, "invalid_user_id")

    if other_id == me.id:
        raise ApiError("不能跟自己傳訊息", 400, "self_conversation")

    other = db.session.get(User, other_id)
    if other is None:
        raise ApiError("找不到這個使用者", 404, "not_found")

    conv = _find_direct_conversation(me.id, other_id)
    if conv is None:
        conv = Conversation()
        db.session.add(conv)
        db.session.flush()
        db.session.add(ConversationMember(conversation_id=conv.id, user_id=me.id))
        db.session.add(ConversationMember(conversation_id=conv.id, user_id=other_id))
        db.session.commit()

    return jsonify({"conversation": conversation_to_dict(conv, me.id)}), 201


@messages_bp.route("/messages/conversations/<int:conversation_id>", methods=["GET"])
@login_required
def get_messages(conversation_id: int):
    """取得訊息。帶 after_id 時只回傳比它新的訊息（輪詢用）。"""
    me = current_user()
    conv = db.session.get(Conversation, conversation_id)
    if conv is None:
        raise ApiError("找不到這個對話", 404, "not_found")
    if not _is_member(conversation_id, me.id):
        raise ApiError("你不是這個對話的成員", 403, "forbidden")

    try:
        after_id = int(request.args.get("after_id", 0))
    except (TypeError, ValueError):
        after_id = 0
    try:
        limit = int(request.args.get("limit", 50))
    except (TypeError, ValueError):
        limit = 50
    limit = max(1, min(limit, 100))

    query = select(Message).where(Message.conversation_id == conversation_id)
    if after_id:
        query = query.where(Message.id > after_id)
    messages = db.session.execute(
        query.order_by(Message.id.asc()).limit(limit)
    ).scalars().all()

    # 把已讀時間推進到最新訊息
    if messages:
        member = db.session.execute(
            select(ConversationMember).where(
                ConversationMember.conversation_id == conversation_id,
                ConversationMember.user_id == me.id,
            )
        ).scalar_one_or_none()
        if member is not None:
            member.last_read_at = messages[-1].created_at
            db.session.commit()

    return jsonify({"messages": [message_to_dict(m) for m in messages]})


@messages_bp.route("/messages/conversations/<int:conversation_id>", methods=["POST"])
@login_required
def send_message(conversation_id: int):
    me = current_user()
    conv = db.session.get(Conversation, conversation_id)
    if conv is None:
        raise ApiError("找不到這個對話", 404, "not_found")
    if not _is_member(conversation_id, me.id):
        raise ApiError("你不是這個對話的成員", 403, "forbidden")

    data = request.get_json(silent=True) or {}
    body = str(data.get("body") or "").strip()
    if not body:
        raise ApiError("訊息不能是空的", 400, "empty_message")
    if len(body) > 5000:
        raise ApiError("訊息最多 5000 字元", 400, "content_too_long")

    now = datetime.now(timezone.utc)
    message = Message(
        conversation_id=conversation_id, sender_id=me.id, body=body, created_at=now
    )
    db.session.add(message)
    conv.last_message_at = now

    # 通知對方
    other = db.session.execute(
        select(ConversationMember.user_id).where(
            ConversationMember.conversation_id == conversation_id,
            ConversationMember.user_id != me.id,
        )
    ).scalar_one_or_none()
    if other is not None:
        db.session.add(
            Notification(
                user_id=other,
                actor_id=me.id,
                type="message",
                target_type="conversation",
                target_id=conversation_id,
            )
        )

    db.session.commit()

    # 收件者是 NPC 時，在背景呼叫 opencode 產生回覆
    # （不阻塞這個請求，前端靠 3 秒輪詢取得回覆）
    if other is not None and npc_service.is_npc(other):
        npc_service.spawn_reply(
            current_app._get_current_object(),
            conversation_id=conversation_id,
            npc_user_id=other,
            user_message=body,
        )

    return jsonify({"message": message_to_dict(message)}), 201
