"""使用者 API。"""

from __future__ import annotations

from flask import Blueprint, jsonify, request
from sqlalchemy import func, or_, select

from ..extensions import db
from ..models import Friendship, Post, User
from ..serializers import author_to_dict, posts_to_list
from ..utils import ApiError, current_user, login_required, pagination_args

users_bp = Blueprint("users", __name__, url_prefix="/api")


def _pair(a: int, b: int) -> tuple[int, int]:
    """好友表的 user_a_id 一定要小於 user_b_id。"""
    return (a, b) if a < b else (b, a)


@users_bp.route("/users/<int:user_id>", methods=["GET"])
@login_required
def get_user(user_id: int):
    user = db.session.get(User, user_id)
    if user is None:
        raise ApiError("找不到這個使用者", 404, "not_found")

    post_count = (
        db.session.execute(select(func.count(Post.id)).where(Post.user_id == user_id))
        .scalar_one()
    )
    friend_count = (
        db.session.execute(
            select(func.count(Friendship.id)).where(
                or_(Friendship.user_a_id == user_id, Friendship.user_b_id == user_id)
            )
        ).scalar_one()
    )

    return jsonify(
        {
            "user": user.to_dict(),
            "stats": {"post_count": post_count, "friend_count": friend_count},
        }
    )


@users_bp.route("/users/me", methods=["PATCH"])
@login_required
def update_me():
    me = current_user()
    data = request.get_json(silent=True) or {}

    display_name = data.get("display_name")
    if display_name is not None:
        display_name = str(display_name).strip()
        if not display_name or len(display_name) > 100:
            raise ApiError("顯示名稱長度需介於 1-100 字元", 400, "invalid_display_name")
        me.display_name = display_name

    bio = data.get("bio")
    if bio is not None:
        bio = str(bio).strip()
        if len(bio) > 500:
            raise ApiError("簡介最多 500 字元", 400, "invalid_bio")
        me.bio = bio or None

    avatar_url = data.get("avatar_url")
    if avatar_url is not None:
        avatar_url = str(avatar_url).strip()
        me.avatar_url = avatar_url or None

    db.session.commit()
    return jsonify({"user": me.to_dict(include_email=True)})


@users_bp.route("/users/<int:user_id>/posts", methods=["GET"])
@login_required
def user_posts(user_id: int):
    user = db.session.get(User, user_id)
    if user is None:
        raise ApiError("找不到這個使用者", 404, "not_found")
    return _posts_response(user.id)


@users_bp.route("/users/me/posts", methods=["GET"])
@login_required
def my_posts():
    """自己的貼文（前端個人頁 / 「我的貼文」分頁用）。"""
    me = current_user()
    return _posts_response(me.id)


def _posts_response(user_id: int):
    offset, limit = pagination_args()
    total = (
        db.session.execute(select(func.count(Post.id)).where(Post.user_id == user_id))
        .scalar_one()
    )
    posts = db.session.execute(
        select(Post)
        .where(Post.user_id == user_id)
        .order_by(Post.created_at.desc(), Post.id.desc())
        .offset(offset)
        .limit(limit)
    ).scalars().all()

    viewer = current_user()
    return jsonify(
        {
            "posts": posts_to_list(list(posts), viewer.id if viewer else None),
            "pagination": {
                "page": offset // limit + 1,
                "limit": limit,
                "total": total,
                "has_more": offset + len(posts) < total,
            },
        }
    )


@users_bp.route("/users/me/friends", methods=["GET"])
@login_required
def my_friends():
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
