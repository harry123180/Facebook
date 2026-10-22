"""資料模型（SQLAlchemy 2.0）。

這份檔案是前後端的契約，改動前請先更新 PRD。
設計原則：
- 時間欄位一律用 TIMESTAMP WITH TIME ZONE (UTC)，顯示層再轉本地時區。
- 密碼存雜湊、驗證碼存雜湊，DB 明文不出現任何秘密。
- likes / friendships 用 unique constraint 防止重複，靠 DB 擋 race condition。
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .extensions import db


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


# --------------------------------------------------------------------------
# 使用者
# --------------------------------------------------------------------------
class User(db.Model):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # 一律存小寫，unique 之後就等同 case-insensitive
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    avatar_url: Mapped[str | None] = mapped_column(String(500))
    bio: Mapped[str | None] = mapped_column(String(500))
    is_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now()
    )
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    posts: Mapped[list["Post"]] = relationship(
        back_populates="author", cascade="all, delete-orphan", passive_deletes=True
    )
    comments: Mapped[list["Comment"]] = relationship(
        back_populates="author", cascade="all, delete-orphan", passive_deletes=True
    )

    __table_args__ = (
        # username 只允許英數字與底線
        CheckConstraint(
            "username ~ '^[A-Za-z0-9_]{3,30}$'", name="ck_users_username_format"
        ),
        # 全文搜尋用 trigram（支援中文子字串搜尋）
        Index("ix_users_display_name_trgm", "display_name", postgresql_using="gin",
              postgresql_ops={"display_name": "gin_trgm_ops"}),
        Index("ix_users_username_trgm", "username", postgresql_using="gin",
              postgresql_ops={"username": "gin_trgm_ops"}),
    )

    def to_dict(self, *, include_email: bool = False) -> dict:
        data = {
            "id": self.id,
            "username": self.username,
            "display_name": self.display_name,
            "avatar_url": self.avatar_url,
            "bio": self.bio,
            "is_verified": self.is_verified,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
        if include_email:
            data["email"] = self.email
        return data


# --------------------------------------------------------------------------
# Email 驗證碼
# --------------------------------------------------------------------------
class EmailVerificationCode(db.Model):
    """6 位數驗證碼。

    密碼不存明文：DB 存 sha256(code + salt)，salt 存在同一列。
    驗證時用同樣方式雜湊後比對。
    """

    __tablename__ = "email_verification_codes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    code_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    salt: Mapped[str] = mapped_column(String(32), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now()
    )

    user: Mapped["User"] = relationship()

    __table_args__ = (
        Index("ix_verify_user_active", "user_id", "used_at"),
    )


# --------------------------------------------------------------------------
# 貼文
# --------------------------------------------------------------------------
class Post(db.Model):
    __tablename__ = "posts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now()
    )

    author: Mapped["User"] = relationship(back_populates="posts")
    images: Mapped[list["PostImage"]] = relationship(
        back_populates="post",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="PostImage.position",
    )
    comments: Mapped[list["Comment"]] = relationship(
        back_populates="post", cascade="all, delete-orphan", passive_deletes=True
    )
    likes: Mapped[list["Like"]] = relationship(
        back_populates="post", cascade="all, delete-orphan", passive_deletes=True
    )

    __table_args__ = (
        # 動態牆：全域依時間倒序
        Index("ix_posts_created_at", "created_at"),
        # 個人頁：該使用者貼文分頁
        Index("ix_posts_user_created", "user_id", "created_at"),
        Index("ix_posts_content_trgm", "content", postgresql_using="gin",
              postgresql_ops={"content": "gin_trgm_ops"}),
    )


class PostImage(db.Model):
    """貼文附圖。

    來源可能是使用者貼的外部網址，也可能是上傳的檔案（存 static/uploads）。
    統一存成相對路徑或完整 URL，由前端負責組出可存取的位置。
    """

    __tablename__ = "post_images"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    post_id: Mapped[int] = mapped_column(
        ForeignKey("posts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    url: Mapped[str] = mapped_column(String(500), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now()
    )

    post: Mapped["Post"] = relationship(back_populates="images")


# --------------------------------------------------------------------------
# 按讚
# --------------------------------------------------------------------------
class Like(db.Model):
    __tablename__ = "likes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    post_id: Mapped[int] = mapped_column(
        ForeignKey("posts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now()
    )

    post: Mapped["Post"] = relationship(back_populates="likes")
    user: Mapped["User"] = relationship()

    __table_args__ = (
        UniqueConstraint("user_id", "post_id", name="uq_likes_user_post"),
    )


# --------------------------------------------------------------------------
# 留言
# --------------------------------------------------------------------------
class Comment(db.Model):
    __tablename__ = "comments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    post_id: Mapped[int] = mapped_column(
        ForeignKey("posts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    # 回覆某則留言（Facebook 式 thread reply），NULL 代表是頂層留言
    parent_id: Mapped[int | None] = mapped_column(
        ForeignKey("comments.id", ondelete="CASCADE"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now()
    )

    author: Mapped["User"] = relationship(back_populates="comments")
    post: Mapped["Post"] = relationship(back_populates="comments")
    replies: Mapped[list["Comment"]] = relationship(
        back_populates="parent", cascade="all, delete-orphan"
    )
    parent: Mapped["Comment | None"] = relationship(
        back_populates="replies", remote_side=[id]
    )

    __table_args__ = (
        Index("ix_comments_post_created", "post_id", "created_at"),
    )


# --------------------------------------------------------------------------
# 好友
# --------------------------------------------------------------------------
class FriendRequest(db.Model):
    """好友請求。接受後另外寫入 friendships。

    status: pending / accepted / declined
    declined 的紀錄保留，避免使用者重複發送造成多筆 pending。
    """

    __tablename__ = "friend_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    sender_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    receiver_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending", server_default="pending"
    )
    message: Mapped[str | None] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now()
    )
    responded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    sender: Mapped["User"] = relationship(foreign_keys=[sender_id])
    receiver: Mapped["User"] = relationship(foreign_keys=[receiver_id])

    __table_args__ = (
        UniqueConstraint("sender_id", "receiver_id", name="uq_friendreq_pair"),
        CheckConstraint("status in ('pending','accepted','declined')", name="ck_friendreq_status"),
        Index("ix_friendreq_receiver_status", "receiver_id", "status"),
    )


class Friendship(db.Model):
    """好友關係（雙向）。user_a_id < user_b_id，用來確保唯一性。"""

    __tablename__ = "friendships"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_a_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_b_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now()
    )

    __table_args__ = (
        UniqueConstraint("user_a_id", "user_b_id", name="uq_friendship_pair"),
        CheckConstraint("user_a_id < user_b_id", name="ck_friendship_ordering"),
    )


# --------------------------------------------------------------------------
# 通知
# --------------------------------------------------------------------------
class Notification(db.Model):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # 收到通知的人
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # 觸發通知的人（自己按自己的讚不通知）
    actor_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    type: Mapped[str] = mapped_column(String(30), nullable=False)
    # type: like | comment | friend_request | friend_accept | message
    # target_type: post | comment | user | conversation
    target_type: Mapped[str | None] = mapped_column(String(20))
    target_id: Mapped[int | None] = mapped_column(Integer)
    is_read: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now()
    )

    actor: Mapped["User | None"] = relationship(foreign_keys=[actor_id])

    __table_args__ = (
        Index("ix_notifications_user_created", "user_id", "created_at"),
        Index("ix_notifications_user_unread", "user_id", "is_read"),
    )


# --------------------------------------------------------------------------
# NPC 角色
# --------------------------------------------------------------------------
class NpcProfile(db.Model):
    """NPC（AI 角色）設定。

    一個 NPC 就是一個真的 users 資料列，所以能正常走好友、訊息、通知等流程，
    只是多了一份 persona（角色設定）與 opencode session 的對應。
    """

    __tablename__ = "npc_profiles"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    # 角色設定，會在 opencode session 的第一則訊息裡帶進去
    persona: Mapped[str] = mapped_column(Text, nullable=False)
    # opencode 的模型，格式 provider/model
    model: Mapped[str] = mapped_column(
        String(120), nullable=False, default="ollama/qwen36-nothink"
    )
    # opencode session id（每個 NPC 一個，讓它記得聊天脈絡）
    session_id: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now()
    )

    user: Mapped["User"] = relationship()

    def to_dict(self) -> dict:
        return {
            "user_id": self.user_id,
            "persona": self.persona,
            "model": self.model,
            "has_session": self.session_id is not None,
        }


# --------------------------------------------------------------------------
# 私人訊息
# --------------------------------------------------------------------------
class Conversation(db.Model):
    __tablename__ = "conversations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now()
    )
    # 最後一則訊息時間，方便列表排序
    last_message_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    members: Mapped[list["ConversationMember"]] = relationship(
        back_populates="conversation", cascade="all, delete-orphan", passive_deletes=True
    )
    messages: Mapped[list["Message"]] = relationship(
        back_populates="conversation", cascade="all, delete-orphan", passive_deletes=True
    )


class ConversationMember(db.Model):
    __tablename__ = "conversation_members"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    conversation_id: Mapped[int] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    last_read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    joined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now()
    )

    conversation: Mapped["Conversation"] = relationship(back_populates="members")
    user: Mapped["User"] = relationship()

    __table_args__ = (
        UniqueConstraint("conversation_id", "user_id", name="uq_convmember_pair"),
    )


class Message(db.Model):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    conversation_id: Mapped[int] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    sender_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    body: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now()
    )

    conversation: Mapped["Conversation"] = relationship(back_populates="messages")
    sender: Mapped["User"] = relationship()

    __table_args__ = (
        # 短輪詢用：取某對話最新的訊息
        Index("ix_messages_conv_id_desc", "conversation_id", "id"),
    )
