"""把 ORM 物件轉成 API 回應用的 dict。

特別注意：post 的 like_count / comment_count 必須用一次彙總查詢取得，
不要在迴圈裡對每篇貼文各查一次（會變成 N+1 query）。
"""

from __future__ import annotations

from sqlalchemy import func, select

from .extensions import db
from .models import Comment, Conversation, ConversationMember, Like, Message, Notification, Post, User


def user_to_dict(user: User, *, include_email: bool = False) -> dict:
    return user.to_dict(include_email=include_email)


def author_to_dict(user: User) -> dict:
    """貼文/留言上的作者，精簡欄位。"""
    return {
        "id": user.id,
        "username": user.username,
        "display_name": user.display_name,
        "avatar_url": user.avatar_url,
    }


def comment_to_dict(comment: Comment) -> dict:
    return {
        "id": comment.id,
        "content": comment.content,
        "created_at": comment.created_at.isoformat() if comment.created_at else None,
        "parent_id": comment.parent_id,
        "author": author_to_dict(comment.author),
    }


def notification_to_dict(n: Notification) -> dict:
    return {
        "id": n.id,
        "type": n.type,
        "target_type": n.target_type,
        "target_id": n.target_id,
        "is_read": n.is_read,
        "created_at": n.created_at.isoformat() if n.created_at else None,
        "actor": author_to_dict(n.actor) if n.actor else None,
    }


def message_to_dict(m: Message) -> dict:
    return {
        "id": m.id,
        "body": m.body,
        "created_at": m.created_at.isoformat() if m.created_at else None,
        "sender_id": m.sender_id,
    }


def posts_to_list(posts: list[Post], viewer_id: int | None) -> list[dict]:
    """批次把貼文轉成 dict，含讚數、留言數、是否已按讚。

    三次彙總查詢搞定整頁，不會變成 N+1。
    """
    if not posts:
        return []

    post_ids = [p.id for p in posts]

    like_rows = db.session.execute(
        select(Like.post_id, func.count(Like.id))
        .where(Like.post_id.in_(post_ids))
        .group_by(Like.post_id)
    ).all()
    like_counts = {pid: cnt for pid, cnt in like_rows}

    comment_rows = db.session.execute(
        select(Comment.post_id, func.count(Comment.id))
        .where(Comment.post_id.in_(post_ids))
        .group_by(Comment.post_id)
    ).all()
    comment_counts = {pid: cnt for pid, cnt in comment_rows}

    liked: set[int] = set()
    if viewer_id is not None:
        liked = set(
            db.session.execute(
                select(Like.post_id).where(
                    Like.post_id.in_(post_ids), Like.user_id == viewer_id
                )
            ).scalars()
        )

    return [
        {
            "id": p.id,
            "content": p.content,
            "created_at": p.created_at.isoformat() if p.created_at else None,
            "author": author_to_dict(p.author),
            "images": [
                {"id": img.id, "url": img.url, "position": img.position}
                for img in p.images
            ],
            "like_count": like_counts.get(p.id, 0),
            "comment_count": comment_counts.get(p.id, 0),
            "liked_by_me": p.id in liked,
        }
        for p in posts
    ]


def conversation_to_dict(conv: Conversation, viewer_id: int) -> dict:
    """把對話轉成前端要的形狀：對方、最後一則訊息、未讀數。"""
    me = db.session.execute(
        select(ConversationMember).where(
            ConversationMember.conversation_id == conv.id,
            ConversationMember.user_id == viewer_id,
        )
    ).scalar_one_or_none()
    other = (
        db.session.execute(
            select(User)
            .join(ConversationMember, ConversationMember.user_id == User.id)
            .where(
                ConversationMember.conversation_id == conv.id,
                ConversationMember.user_id != viewer_id,
            )
        )
        .scalars()
        .first()
    )

    last_message = (
        db.session.execute(
            select(Message)
            .where(Message.conversation_id == conv.id)
            .order_by(Message.id.desc())
            .limit(1)
        )
        .scalar_one_or_none()
    )

    unread = 0
    if me is not None and me.last_read_at is not None:
        unread = (
            db.session.execute(
                select(func.count(Message.id)).where(
                    Message.conversation_id == conv.id,
                    Message.sender_id != viewer_id,
                    Message.created_at > me.last_read_at,
                )
            )
            .scalar_one()
        )
    else:
        unread = (
            db.session.execute(
                select(func.count(Message.id)).where(
                    Message.conversation_id == conv.id,
                    Message.sender_id != viewer_id,
                )
            )
            .scalar_one()
        )

    return {
        "id": conv.id,
        "other_user": author_to_dict(other) if other else None,
        "last_message": message_to_dict(last_message) if last_message else None,
        "last_message_at": (
            conv.last_message_at.isoformat() if conv.last_message_at else None
        ),
        "unread_count": unread,
    }
