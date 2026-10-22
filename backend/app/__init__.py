"""Flask 應用程式工廠。"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory
from flask.sessions import SecureCookieSessionInterface

from .config import get_config
from .extensions import cors, db, migrate
from . import models  # noqa: F401  必須 import 才會註冊所有 table 給 SQLAlchemy metadata

logger = logging.getLogger(__name__)

# frontend build 產物（Vite 輸出到 frontend/dist）
FRONTEND_DIST = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"


class TunnelAwareSessionInterface(SecureCookieSessionInterface):
    """依實際對外連線協定決定 session cookie 是否標記 Secure。

    走 cloudflared Quick Tunnel 時，瀏覽器 -> Cloudflare 是 HTTPS，
    但 Cloudflare -> 本機 Flask 是 HTTP。若一律用 SESSION_COOKIE_SECURE=1，
    本機 http://127.0.0.1:8000 測試時 cookie 會被瀏覽器擋掉。

    偵測順序：
      1. X-Forwarded-Proto: https        （一般反向代理 / nginx）
      2. Cf-Visitor: {"scheme":"https"}   （Cloudflare 實際使用的 header）
      3. request.is_secure               （本機就是 HTTPS）
    """

    @staticmethod
    def _external_is_https(req) -> bool:
        if req.is_secure:
            return True

        forwarded = req.headers.get("X-Forwarded-Proto", "").split(",")[0].strip().lower()
        if forwarded == "https":
            return True
        if req.headers.get("X-Forwarded-Ssl", "").lower() == "on":
            return True

        # Cloudflare 用 Cf-Visitor 標示原始協定
        cf_visitor = req.headers.get("Cf-Visitor", "")
        if cf_visitor:
            try:
                if json.loads(cf_visitor).get("scheme", "").lower() == "https":
                    return True
            except (ValueError, AttributeError):
                pass

        return False

    def get_cookie_secure(self, app):
        # SESSION_COOKIE_SECURE 明確指定時優先；否則自動判斷對外協定
        explicit = app.config.get("SESSION_COOKIE_SECURE")
        if explicit in (True, "1", "true", "True"):
            return True
        if explicit in (False, "0", "false", "False"):
            return False
        return self._external_is_https(request)


def create_app(config_name: str | None = None) -> Flask:
    app = Flask(__name__, static_folder=None)
    app.session_interface = TunnelAwareSessionInterface()

    cfg = get_config()
    app.config.from_object(cfg)
    if config_name:
        app.config.from_object(config_name)

    db.init_app(app)
    migrate.init_app(app, db)
    # 單一 origin 架構下其實不需要 CORS，但保留給 Vite dev server 直連時除錯用
    cors.init_app(
        app,
        resources={r"/api/*": {"origins": [app.config["FRONTEND_ORIGIN"]]}},
        supports_credentials=True,
    )

    _register_blueprints(app)
    _register_error_handlers(app)
    _register_static(app)

    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    @app.get("/api/health")
    def health():
        return jsonify({"status": "ok", "service": "facebook-mvp"})

    logger.info("Facebook MVP app created (debug=%s)", app.config.get("DEBUG"))
    return app


def _register_blueprints(app: Flask) -> None:
    from .api.auth import auth_bp
    from .api.friends import friends_bp
    from .api.messages import messages_bp
    from .api.notifications import notifications_bp
    from .api.npc import npc_bp
    from .api.posts import posts_bp
    from .api.search import search_bp
    from .api.uploads import uploads_bp
    from .api.users import users_bp

    for bp in (
        auth_bp,
        users_bp,
        posts_bp,
        friends_bp,
        notifications_bp,
        messages_bp,
        search_bp,
        uploads_bp,
        npc_bp,
    ):
        app.register_blueprint(bp)


def _register_error_handlers(app: Flask) -> None:
    from .utils import ApiError

    @app.errorhandler(ApiError)
    def handle_api_error(error):
        return jsonify({"error": error.code, "message": error.message}), error.status

    @app.errorhandler(404)
    def not_found(e):
        # /api 底下的 404 一律回 JSON，不要掉進 SPA fallback
        from flask import request

        if request.path.startswith("/api/"):
            return jsonify({"error": "not_found", "message": "找不到這個資源"}), 404
        return _serve_index(app)

    @app.errorhandler(413)
    def too_large(e):
        limit_mb = app.config["MAX_CONTENT_LENGTH"] // (1024 * 1024)
        return jsonify({"error": "file_too_large", "message": f"檔案超過 {limit_mb}MB 上限"}), 413

    @app.errorhandler(500)
    def server_error(e):
        logger.exception("Unhandled server error")
        return jsonify({"error": "internal_error", "message": "伺服器發生錯誤"}), 500

    @app.errorhandler(Exception)
    def unhandled(e):
        from werkzeug.exceptions import HTTPException

        if isinstance(e, HTTPException):
            return jsonify({"error": e.name.lower().replace(" ", "_"), "message": e.description}), e.code
        logger.exception("Unhandled exception")
        return jsonify({"error": "internal_error", "message": "伺服器發生錯誤"}), 500


def _serve_index(app: Flask):
    index = FRONTEND_DIST / "index.html"
    if index.exists():
        return send_from_directory(FRONTEND_DIST, "index.html")
    return (
        "<h1>Facebook MVP API</h1>"
        "<p>前端尚未 build。開發請用 <code>cd frontend &amp;&amp; pnpm dev</code>；"
        "正式請執行 <code>pnpm build</code>。</p>",
        200,
    )


def _register_static(app: Flask) -> None:
    """提供上傳檔案與 React 靜態檔，並做 SPA 深層路由 fallback。"""

    @app.get("/static/uploads/<path:filename>")
    def uploaded_file(filename: str):
        return send_from_directory(app.config["UPLOAD_FOLDER"], filename)

    @app.get("/", defaults={"path": ""})
    @app.get("/<path:path>")
    def serve_frontend(path: str):
        if path.startswith("api/"):
            return jsonify({"error": "not_found", "message": "找不到這個 API"}), 404

        # 靜態資源存在就直接送；不存在就 fallback 到 index.html 讓 React Router 接手
        candidate = FRONTEND_DIST / path
        if path and candidate.is_file():
            return send_from_directory(FRONTEND_DIST, path)
        return _serve_index(app)
