from .auth import auth_bp
from .friends import friends_bp
from .messages import messages_bp
from .notifications import notifications_bp
from .posts import posts_bp
from .search import search_bp
from .uploads import uploads_bp
from .users import users_bp

__all__ = [
    "auth_bp", "users_bp", "posts_bp", "friends_bp",
    "notifications_bp", "messages_bp", "search_bp", "uploads_bp",
]
