"""搜尋 API：使用者 + 貼文。

用 pg_trgm + ILIKE 做子字串比對（比 tsvector 更適合中文）。
"""

from __future__ import annotations

from flask import Blueprint, jsonify, request
from sqlalchemy import or_, select

from ..extensions import db
from ..models import Post, User
from ..serializers import author_to_dict, posts_to_list
from ..utils import ApiError, current_user, login_required

search_bp = Blueprint("search", __name__, url_prefix="/api")


@search_bp.route("/search", methods=["GET"])
@login_required
def search():
    me = current_user()
    q = (request.args.get("q") or "").strip()
    kind = (request.args.get("type") or "all").lower()

    if kind not in ("all", "users", "posts"):
        raise ApiError("type 只能是 all / users / posts", 400, "invalid_type")

    result: dict = {"users": [], "posts": []}

    if not q:
        return jsonify(result)

    pattern = f"%{q}%"

    if kind in ("all", "users"):
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
            .limit(20)
        ).scalars().all()
        result["users"] = [author_to_dict(u) for u in users]

    if kind in ("all", "posts"):
        posts = db.session.execute(
            select(Post)
            .where(Post.content.ilike(pattern))
            .order_by(Post.created_at.desc(), Post.id.desc())
            .limit(20)
        ).scalars().all()
        result["posts"] = posts_to_list(list(posts), me.id)

    return jsonify(result)
