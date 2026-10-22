"""通知 API。"""

from __future__ import annotations

from flask import Blueprint, jsonify
from sqlalchemy import func, select, update

from ..extensions import db
from ..models import Notification
from ..serializers import notification_to_dict
from ..utils import ApiError, current_user, login_required, pagination_args

notifications_bp = Blueprint("notifications", __name__, url_prefix="/api")


@notifications_bp.route("/notifications", methods=["GET"])
@login_required
def list_notifications():
    me = current_user()
    offset, limit = pagination_args()

    total = (
        db.session.execute(
            select(func.count(Notification.id)).where(Notification.user_id == me.id)
        )
        .scalar_one()
    )
    unread_count = (
        db.session.execute(
            select(func.count(Notification.id)).where(
                Notification.user_id == me.id, Notification.is_read.is_(False)
            )
        )
        .scalar_one()
    )

    notifications = db.session.execute(
        select(Notification)
        .where(Notification.user_id == me.id)
        .order_by(Notification.created_at.desc(), Notification.id.desc())
        .offset(offset)
        .limit(limit)
    ).scalars().all()

    return jsonify(
        {
            "notifications": [notification_to_dict(n) for n in notifications],
            "unread_count": unread_count,
            "pagination": {
                "page": offset // limit + 1,
                "limit": limit,
                "total": total,
                "has_more": offset + len(notifications) < total,
            },
        }
    )


@notifications_bp.route("/notifications/<int:notification_id>/read", methods=["POST"])
@login_required
def mark_read(notification_id: int):
    me = current_user()
    n = db.session.get(Notification, notification_id)
    if n is None:
        raise ApiError("找不到這則通知", 404, "not_found")
    if n.user_id != me.id:
        raise ApiError("不能操作別人的通知", 403, "forbidden")

    n.is_read = True
    db.session.commit()
    return jsonify({"notification": notification_to_dict(n)})


@notifications_bp.route("/notifications/read-all", methods=["POST"])
@login_required
def mark_all_read():
    me = current_user()
    db.session.execute(
        update(Notification)
        .where(Notification.user_id == me.id, Notification.is_read.is_(False))
        .values(is_read=True)
    )
    db.session.commit()
    return jsonify({"unread_count": 0})
