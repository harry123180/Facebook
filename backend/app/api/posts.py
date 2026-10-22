"""貼文、留言、按讚 API。"""

from __future__ import annotations

from flask import Blueprint, jsonify, request
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from ..extensions import db
from ..models import Comment, Like, Notification, Post, PostImage, User
from ..serializers import comment_to_dict, posts_to_list
from ..utils import ApiError, current_user, login_required, pagination_args

posts_bp = Blueprint("posts", __name__, url_prefix="/api")


def _get_post_or_404(post_id: int) -> Post:
    post = db.session.get(Post, post_id)
    if post is None:
        raise ApiError("找不到這則貼文", 404, "not_found")
    return post


@posts_bp.route("/posts", methods=["GET"])
@login_required
def list_posts():
    """全域動態牆，依發布時間倒序。"""
    offset, limit = pagination_args()
    total = db.session.execute(select(func.count(Post.id))).scalar_one()

    posts = db.session.execute(
        select(Post)
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


@posts_bp.route("/posts", methods=["POST"])
@login_required
def create_post():
    me = current_user()
    data = request.get_json(silent=True) or {}

    content = str(data.get("content") or "").strip()
    image_urls = data.get("image_urls") or []
    if isinstance(image_urls, str):
        image_urls = [image_urls]
    image_urls = [str(u).strip() for u in image_urls if str(u).strip()]

    if not content and not image_urls:
        raise ApiError("貼文內容不能是空的", 400, "empty_post")
    if len(content) > 5000:
        raise ApiError("貼文內容最多 5000 字元", 400, "content_too_long")
    if len(image_urls) > 10:
        raise ApiError("一則貼文最多 10 張圖片", 400, "too_many_images")

    post = Post(user_id=me.id, content=content)
    db.session.add(post)
    db.session.flush()

    for idx, url in enumerate(image_urls):
        db.session.add(PostImage(post_id=post.id, url=url, position=idx))

    db.session.commit()
    return jsonify({"post": posts_to_list([post], me.id)[0]}), 201


@posts_bp.route("/posts/<int:post_id>", methods=["GET"])
@login_required
def get_post(post_id: int):
    post = _get_post_or_404(post_id)
    viewer = current_user()
    return jsonify({"post": posts_to_list([post], viewer.id if viewer else None)[0]})


@posts_bp.route("/posts/<int:post_id>", methods=["DELETE"])
@login_required
def delete_post(post_id: int):
    me = current_user()
    post = _get_post_or_404(post_id)
    if post.user_id != me.id:
        raise ApiError("只能刪除自己的貼文", 403, "forbidden")
    db.session.delete(post)
    db.session.commit()
    return "", 204


@posts_bp.route("/posts/<int:post_id>/like", methods=["POST"])
@login_required
def like_post(post_id: int):
    me = current_user()
    post = _get_post_or_404(post_id)

    existing = db.session.execute(
        select(Like).where(Like.user_id == me.id, Like.post_id == post.id)
    ).scalar_one_or_none()

    if existing is None:
        like = Like(user_id=me.id, post_id=post.id)
        db.session.add(like)
        try:
            db.session.flush()
        except IntegrityError:
            # race condition：別人剛好也按了讚，unique constraint 擋下來
            db.session.rollback()
            return jsonify(
                {"post": posts_to_list([_get_post_or_404(post_id)], me.id)[0], "liked": True}
            )

        # 自己按自己的讚不通知
        if post.user_id != me.id:
            db.session.add(
                Notification(
                    user_id=post.user_id,
                    actor_id=me.id,
                    type="like",
                    target_type="post",
                    target_id=post.id,
                )
            )
        db.session.commit()

    return jsonify({"post": posts_to_list([post], me.id)[0], "liked": True})


@posts_bp.route("/posts/<int:post_id>/like", methods=["DELETE"])
@login_required
def unlike_post(post_id: int):
    me = current_user()
    post = _get_post_or_404(post_id)

    existing = db.session.execute(
        select(Like).where(Like.user_id == me.id, Like.post_id == post.id)
    ).scalar_one_or_none()
    if existing is not None:
        db.session.delete(existing)
        db.session.commit()

    return jsonify({"post": posts_to_list([post], me.id)[0], "liked": False})


@posts_bp.route("/posts/<int:post_id>/comments", methods=["GET"])
@login_required
def list_comments(post_id: int):
    post = _get_post_or_404(post_id)
    offset, limit = pagination_args()
    total = (
        db.session.execute(
            select(func.count(Comment.id)).where(Comment.post_id == post.id)
        )
        .scalar_one()
    )
    comments = db.session.execute(
        select(Comment)
        .where(Comment.post_id == post.id)
        .order_by(Comment.created_at.asc(), Comment.id.asc())
        .offset(offset)
        .limit(limit)
    ).scalars().all()

    return jsonify(
        {
            "comments": [comment_to_dict(c) for c in comments],
            "pagination": {
                "page": offset // limit + 1,
                "limit": limit,
                "total": total,
                "has_more": offset + len(comments) < total,
            },
        }
    )


@posts_bp.route("/posts/<int:post_id>/comments", methods=["POST"])
@login_required
def create_comment(post_id: int):
    me = current_user()
    post = _get_post_or_404(post_id)
    data = request.get_json(silent=True) or {}

    content = str(data.get("content") or "").strip()
    if not content:
        raise ApiError("留言不能是空的", 400, "empty_comment")
    if len(content) > 2000:
        raise ApiError("留言最多 2000 字元", 400, "content_too_long")

    parent_id = data.get("parent_id")
    if parent_id is not None:
        parent = db.session.get(Comment, int(parent_id))
        if parent is None or parent.post_id != post.id:
            raise ApiError("要回覆的留言不存在", 404, "not_found")
        parent_id = parent.id

    comment = Comment(
        user_id=me.id, post_id=post.id, content=content, parent_id=parent_id
    )
    db.session.add(comment)
    db.session.flush()

    # 自己留言自己的貼文不通知
    if post.user_id != me.id:
        db.session.add(
            Notification(
                user_id=post.user_id,
                actor_id=me.id,
                type="comment",
                target_type="post",
                target_id=post.id,
            )
        )
    db.session.commit()

    return jsonify({"comment": comment_to_dict(comment)}), 201


@posts_bp.route("/comments/<int:comment_id>", methods=["DELETE"])
@login_required
def delete_comment(comment_id: int):
    me = current_user()
    comment = db.session.get(Comment, comment_id)
    if comment is None:
        raise ApiError("找不到這則留言", 404, "not_found")
    if comment.user_id != me.id:
        raise ApiError("只能刪除自己的留言", 403, "forbidden")
    db.session.delete(comment)
    db.session.commit()
    return "", 204
