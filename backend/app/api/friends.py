"""好友 API：搜尋、送請求、接受/拒絕、取消、解除好友。"""

from __future__ import annotations

from datetime import datetime, timezone

from flask import Blueprint, jsonify, request
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError

from ..extensions import db
from ..models import FriendRequest, Friendship, Notification, User
from ..serializers import author_to_dict
from ..utils import ApiError, current_user, login_required

friends_bp = Blueprint("friends", __name__, url_prefix="/api")


def _pair(a: int, b: int) -> tuple[int, int]:
    """friendships 表要求 user_a_id < user_b_id。"""
    return (a, b) if a < b else (b, a)


def _request_to_dict(req: FriendRequest, direction: str) -> dict:
    other = req.receiver if direction == "received" else req.sender
    return {
        "id": req.id,
        "direction": direction,
        "status": req.status,
        "message": req.message,
        "created_at": req.created_at.isoformat() if req.created_at else None,
        "responded_at": req.responded_at.isoformat() if req.responded_at else None,
        "user": author_to_dict(other) if other else None,
    }


@friends_bp.route("/friends/search", methods=["GET"])
@login_required
def search_users():
    me = current_user()
    q = (request.args.get("q") or "").strip()

    if not q:
        return jsonify({"users": []})

    pattern = f"%{q.lower()}%"
    users = db.session.execute(
        select(User)
        .where(
            User.id != me.id,
            or_(
                User.username.ilike(pattern),
                User.display_name.ilike(pattern),
                User.email.ilike(pattern),
            ),
        )
        .order_by(User.username.asc())
        .limit(25)
    ).scalars().all()

    return jsonify({"users": [author_to_dict(u) for u in users]})


@friends_bp.route("/friends", methods=["GET"])
@login_required
def list_friends():
    me = current_user()
    friendships = db.session.execute(
        select(Friendship).where(
            or_(Friendship.user_a_id == me.id, Friendship.user_b_id == me.id)
        )
    ).scalars().all()

    friends = []
    for f in friendships:
        other_id = f.user_b_id if f.user_a_id == me.id else f.user_a_id
        other = db.session.get(User, other_id)
        if other is not None:
            friends.append(author_to_dict(other))

    return jsonify({"friends": friends})


@friends_bp.route("/friends/requests", methods=["GET"])
@login_required
def list_requests():
    me = current_user()
    received = db.session.execute(
        select(FriendRequest)
        .where(FriendRequest.receiver_id == me.id, FriendRequest.status == "pending")
        .order_by(FriendRequest.created_at.desc())
    ).scalars().all()
    sent = db.session.execute(
        select(FriendRequest)
        .where(FriendRequest.sender_id == me.id, FriendRequest.status == "pending")
        .order_by(FriendRequest.created_at.desc())
    ).scalars().all()

    return jsonify(
        {
            "received": [_request_to_dict(r, "received") for r in received],
            "sent": [_request_to_dict(r, "sent") for r in sent],
        }
    )


@friends_bp.route("/friends/requests", methods=["POST"])
@login_required
def send_request():
    me = current_user()
    data = request.get_json(silent=True) or {}

    try:
        receiver_id = int(data.get("receiver_id"))
    except (TypeError, ValueError):
        raise ApiError("請提供有效的 receiver_id", 400, "invalid_receiver_id")

    if receiver_id == me.id:
        raise ApiError("不能加自己為好友", 400, "self_friend_request")

    receiver = db.session.get(User, receiver_id)
    if receiver is None:
        raise ApiError("找不到這個使用者", 404, "not_found")

    # 已經是好友
    a, b = _pair(me.id, receiver_id)
    already_friend = db.session.execute(
        select(Friendship).where(
            Friendship.user_a_id == a, Friendship.user_b_id == b
        )
    ).scalar_one_or_none()
    if already_friend is not None:
        raise ApiError("你們已經是好友了", 409, "conflict")

    # 已有 pending 請求（不論方向）
    existing = db.session.execute(
        select(FriendRequest).where(
            or_(
                (FriendRequest.sender_id == me.id) & (FriendRequest.receiver_id == receiver_id),
                (FriendRequest.sender_id == receiver_id) & (FriendRequest.receiver_id == me.id),
            ),
            FriendRequest.status == "pending",
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise ApiError("好友請求已經送出了", 409, "conflict")

    message = str(data.get("message") or "").strip() or None
    if message and len(message) > 200:
        raise ApiError("訊息最多 200 字元", 400, "message_too_long")

    req = FriendRequest(
        sender_id=me.id, receiver_id=receiver_id, status="pending", message=message
    )
    db.session.add(req)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        raise ApiError("好友請求已經送出了", 409, "conflict")

    db.session.add(
        Notification(
            user_id=receiver_id,
            actor_id=me.id,
            type="friend_request",
            target_type="user",
            target_id=me.id,
        )
    )
    db.session.commit()

    return jsonify({"request": _request_to_dict(req, "sent")}), 201


@friends_bp.route("/friends/requests/<int:request_id>/accept", methods=["POST"])
@login_required
def accept_request(request_id: int):
    me = current_user()
    req = db.session.get(FriendRequest, request_id)
    if req is None:
        raise ApiError("找不到這個好友請求", 404, "not_found")
    if req.receiver_id != me.id:
        raise ApiError("只能接受送給你的好友請求", 403, "forbidden")
    if req.status != "pending":
        raise ApiError("這個請求已經處理過了", 409, "conflict")

    a, b = _pair(req.sender_id, req.receiver_id)
    friendship = db.session.execute(
        select(Friendship).where(
            Friendship.user_a_id == a, Friendship.user_b_id == b
        )
    ).scalar_one_or_none()
    if friendship is None:
        friendship = Friendship(user_a_id=a, user_b_id=b)
        db.session.add(friendship)
        try:
            db.session.flush()
        except IntegrityError:
            db.session.rollback()
            raise ApiError("你們已經是好友了", 409, "conflict")

    now = datetime.now(timezone.utc)
    req.status = "accepted"
    req.responded_at = now

    # 對方也送過請求給我的話，一併標記為 accepted
    reverse = db.session.execute(
        select(FriendRequest).where(
            FriendRequest.sender_id == me.id,
            FriendRequest.receiver_id == req.sender_id,
            FriendRequest.status == "pending",
        )
    ).scalar_one_or_none()
    if reverse is not None:
        reverse.status = "accepted"
        reverse.responded_at = now

    db.session.add(
        Notification(
            user_id=req.sender_id,
            actor_id=me.id,
            type="friend_accept",
            target_type="user",
            target_id=me.id,
        )
    )
    db.session.commit()

    return jsonify(
        {
            "request": _request_to_dict(req, "received"),
            "friendship": {"user_a_id": a, "user_b_id": b},
        }
    )


@friends_bp.route("/friends/requests/<int:request_id>/decline", methods=["POST"])
@login_required
def decline_request(request_id: int):
    me = current_user()
    req = db.session.get(FriendRequest, request_id)
    if req is None:
        raise ApiError("找不到這個好友請求", 404, "not_found")
    if req.receiver_id != me.id:
        raise ApiError("只能拒絕送給你的好友請求", 403, "forbidden")
    if req.status != "pending":
        raise ApiError("這個請求已經處理過了", 409, "conflict")

    req.status = "declined"
    req.responded_at = datetime.now(timezone.utc)
    db.session.commit()
    return jsonify({"request": _request_to_dict(req, "received")})


@friends_bp.route("/friends/requests/<int:request_id>", methods=["DELETE"])
@login_required
def cancel_request(request_id: int):
    me = current_user()
    req = db.session.get(FriendRequest, request_id)
    if req is None:
        raise ApiError("找不到這個好友請求", 404, "not_found")
    if req.sender_id != me.id:
        raise ApiError("只能取消自己送出的請求", 403, "forbidden")
    if req.status != "pending":
        raise ApiError("這個請求已經處理過了", 409, "conflict")

    db.session.delete(req)
    db.session.commit()
    return "", 204


@friends_bp.route("/friends/<int:user_id>", methods=["DELETE"])
@login_required
def remove_friend(user_id: int):
    me = current_user()
    a, b = _pair(me.id, user_id)
    friendship = db.session.execute(
        select(Friendship).where(
            Friendship.user_a_id == a, Friendship.user_b_id == b
        )
    ).scalar_one_or_none()
    if friendship is None:
        raise ApiError("你們不是好友", 404, "not_found")

    db.session.delete(friendship)
    db.session.commit()
    return "", 204
