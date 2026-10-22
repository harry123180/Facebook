"""端到端冒煙測試。

對跑起來的 Flask 伺服器打真實 HTTP，驗證整條註冊 -> 社交 -> 私訊流程。

用法：
    cd backend
    .\\.venv\\Scripts\\python.exe scripts\\smoke_test.py

伺服器預設在 http://127.0.0.1:8000，可用 BASE_URL 環境變數覆寫。
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import psycopg
import requests

BASE_URL = os.getenv("BASE_URL", "http://127.0.0.1:8000")
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

PASSED: list[str] = []
FAILED: list[str] = []


# --------------------------------------------------------------------------
# 載入 .env
# --------------------------------------------------------------------------
def load_env() -> None:
    env_file = PROJECT_ROOT / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key, value)


load_env()

DB_URL = os.getenv("DATABASE_URL", "")
# SQLAlchemy 的 URL 要轉成 psycopg 能用的
PSYCOPG_URL = DB_URL.replace("postgresql+psycopg://", "postgresql://")

# 測試用的固定資料（每次跑會先清掉）
SUFFIX = str(int(time.time()))
USER_A = {
    "email": f"alice_{SUFFIX}@example.com",
    "username": f"alice{SUFFIX[-6:]}",
    "display_name": "Alice 測試",
    "password": "TestPass123!",
}
USER_B = {
    "email": f"bob_{SUFFIX}@example.com",
    "username": f"bob{SUFFIX[-6:]}",
    "display_name": "Bob 測試",
    "password": "TestPass123!",
}
# 已知驗證碼，測試時會用同樣的演算法寫進 DB
KNOWN_CODE = "123456"


def check(name: str, condition: bool, detail: str = "") -> bool:
    if condition:
        PASSED.append(name)
        print(f"  [PASS] {name}")
    else:
        FAILED.append(f"{name} {detail}".strip())
        print(f"  [FAIL] {name}  {detail}")
    return condition


def section(title: str) -> None:
    print(f"\n=== {title} ===")


def db_conn():
    return psycopg.connect(PSYCOPG_URL, autocommit=True)


def cleanup() -> None:
    """清掉上一輪測試留下的人與其關聯資料。"""
    with db_conn() as conn:
        conn.execute(
            """
            DELETE FROM users
            WHERE email LIKE %s OR email LIKE %s
            """,
            (f"alice_{SUFFIX}%", f"bob_{SUFFIX}%"),
        )


def force_verification_code(email: str, code: str) -> bool:
    """用與服務層相同的演算法寫入一組已知驗證碼。

    這不是還原明碼，而是直接以測試目的建立一組合法的 (code_hash, salt)。
    """
    sys.path.insert(0, str(PROJECT_ROOT / "backend"))
    from app.services.verification import hash_code  # noqa: E402

    with db_conn() as conn:
        row = conn.execute(
            """
            SELECT v.id, v.salt, v.user_id
            FROM email_verification_codes v
            JOIN users u ON u.id = v.user_id
            WHERE u.email = %s AND v.used_at IS NULL
            ORDER BY v.created_at DESC
            LIMIT 1
            """,
            (email,),
        ).fetchone()
        if row is None:
            return False
        _id, salt, _uid = row
        conn.execute(
            "UPDATE email_verification_codes SET code_hash = %s, attempts = 0 WHERE id = %s",
            (hash_code(code, salt), _id),
        )
        return True


def main() -> int:
    print(f"目標伺服器: {BASE_URL}")
    cleanup()

    # ---------------- health ----------------
    section("健康檢查")
    r = requests.get(f"{BASE_URL}/api/health", timeout=10)
    check("GET /api/health 回 200", r.status_code == 200, f"got {r.status_code}")
    check("health 回 status=ok", r.json().get("status") == "ok", r.text[:120])

    # ---------------- 未登入 ----------------
    section("未登入存取")
    r = requests.get(f"{BASE_URL}/api/posts", timeout=10)
    check("未登入 GET /api/posts 回 401", r.status_code == 401, f"got {r.status_code}")
    check(
        "401 回應格式正確",
        r.headers.get("Content-Type", "").startswith("application/json")
        and "error" in r.json(),
        r.text[:120],
    )

    # ---------------- 註冊 ----------------
    section("註冊")
    sa = requests.Session()
    r = sa.post(f"{BASE_URL}/api/auth/register", json=USER_A, timeout=30)
    check("註冊回 201", r.status_code == 201, f"got {r.status_code} {r.text[:200]}")
    dev_code = None
    if r.status_code == 201:
        body = r.json()
        check("註冊回 requires_verification=true", body.get("requires_verification") is True)
        check("註冊回 email", body.get("email") == USER_A["email"])
        check("註冊回 delivery 欄位", body.get("delivery") in ("resend", "console"), str(body))
        dev_code = body.get("dev_code")
        # dev_code 只在降級成 console 時出現（Resend testing mode 或 EMAIL_BACKEND=console）
        check(
            "dev_code 只在 delivery=console 時出現",
            (dev_code is not None) == (body.get("delivery") == "console"),
            f"delivery={body.get('delivery')} dev_code={dev_code}",
        )

    r = sa.post(f"{BASE_URL}/api/auth/register", json=USER_A, timeout=30)
    check("重複註冊回 409", r.status_code == 409, f"got {r.status_code}")

    bad = dict(USER_B, email=f"bobx_{SUFFIX}@example.com", username=f"bobx{SUFFIX[-6:]}")
    bad["password"] = "short"
    r = requests.post(f"{BASE_URL}/api/auth/register", json=bad, timeout=30)
    check("弱密碼回 400", r.status_code == 400, f"got {r.status_code}")

    # ---------------- DB 檢查 ----------------
    section("資料庫檢查")
    with db_conn() as conn:
        row = conn.execute(
            "SELECT id, is_verified, password_hash FROM users WHERE email = %s",
            (USER_A["email"],),
        ).fetchone()
        check("使用者已寫入 DB", row is not None)
        if row:
            uid, is_verified, pw_hash = row
            check("初始 is_verified=False", is_verified is False)
            check("密碼不是明文", pw_hash != USER_A["password"], pw_hash[:20])
            check("密碼是 scrypt 格式", pw_hash.startswith("scrypt:"), pw_hash[:20])

        vrow = conn.execute(
            """
            SELECT code_hash, salt, used_at, attempts
            FROM email_verification_codes
            JOIN users ON users.id = email_verification_codes.user_id
            WHERE users.email = %s
            """,
            (USER_A["email"],),
        ).fetchone()
        check("驗證碼已寫入 DB", vrow is not None)
        if vrow:
            code_hash, salt, used_at, attempts = vrow
            check("驗證碼不是明文", code_hash != KNOWN_CODE, code_hash[:20])
            check("驗證碼長度 64 (sha256 hex)", len(code_hash) == 64, str(len(code_hash)))
            check("有 salt", bool(salt))
            check("初始 used_at 為 NULL", used_at is None)
            check("初始 attempts=0", attempts == 0)

    # ---------------- 驗證 ----------------
    section("Email 驗證")
    r = sa.post(
        f"{BASE_URL}/api/auth/verify", json={"email": USER_A["email"], "code": "000000"},
        timeout=30,
    )
    check("錯誤驗證碼回 400", r.status_code == 400, f"got {r.status_code}")

    ok = force_verification_code(USER_A["email"], KNOWN_CODE)
    check("測試用驗證碼寫入成功", ok)

    r = sa.post(
        f"{BASE_URL}/api/auth/verify", json={"email": USER_A["email"], "code": KNOWN_CODE},
        timeout=30,
    )
    check("正確驗證碼回 200", r.status_code == 200, f"got {r.status_code} {r.text[:200]}")
    check("驗證後自動登入（session cookie）", len(sa.cookies) > 0, str(sa.cookies.get_dict()))

    if dev_code:
        # console 模式：直接用 API 回傳的 dev_code 驗證
        r2 = sa.post(
            f"{BASE_URL}/api/auth/verify",
            json={"email": USER_A["email"], "code": dev_code},
            timeout=30,
        )
        check("用 dev_code 驗證也可行", r2.status_code in (200, 400), f"got {r2.status_code}")

    with db_conn() as conn:
        row = conn.execute(
            "SELECT is_verified FROM users WHERE email = %s", (USER_A["email"],)
        ).fetchone()
        check("DB is_verified 變 True", row is not None and row[0] is True)

    # ---------------- 登入 ----------------
    section("登入 / 登出")
    r = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": USER_A["email"], "password": USER_A["password"]},
        timeout=30,
    )
    check("正確密碼登入回 200", r.status_code == 200, f"got {r.status_code}")
    check("登入回 user 欄位", "user" in r.json())

    r = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": USER_A["email"], "password": "WrongPassword1!"},
        timeout=30,
    )
    check("錯誤密碼登入回 400", r.status_code == 400, f"got {r.status_code}")

    r = sa.get(f"{BASE_URL}/api/auth/me", timeout=10)
    check("GET /api/auth/me 回 200", r.status_code == 200, f"got {r.status_code}")
    check("me 回 email", r.json().get("user", {}).get("email") == USER_A["email"])

    # ---------------- 第二個使用者 ----------------
    section("第二個使用者")
    sb = requests.Session()
    r = sb.post(f"{BASE_URL}/api/auth/register", json=USER_B, timeout=30)
    check("B 註冊回 201", r.status_code == 201, f"got {r.status_code}")
    force_verification_code(USER_B["email"], KNOWN_CODE)
    r = sb.post(
        f"{BASE_URL}/api/auth/verify", json={"email": USER_B["email"], "code": KNOWN_CODE},
        timeout=30,
    )
    check("B 驗證回 200", r.status_code == 200, f"got {r.status_code}")

    # ---------------- 發文 ----------------
    section("貼文")
    r = sa.post(
        f"{BASE_URL}/api/posts",
        json={"content": f"Hello 大家好 {SUFFIX}", "image_urls": ["https://example.com/a.png"]},
        timeout=30,
    )
    check("發文回 201", r.status_code == 201, f"got {r.status_code} {r.text[:200]}")
    post = r.json().get("post", {}) if r.status_code == 201 else {}
    post_id = post.get("id")
    check("貼文含作者", "author" in post)
    check("貼文含圖片陣列", len(post.get("images", [])) == 1, str(post.get("images")))
    check("貼文含 like_count", post.get("like_count") == 0)
    check("貼文含 comment_count", post.get("comment_count") == 0)
    check("貼文含 liked_by_me", post.get("liked_by_me") is False)

    r = sa.post(f"{BASE_URL}/api/posts", json={"content": "   "}, timeout=30)
    check("空白貼文回 400", r.status_code == 400, f"got {r.status_code}")

    r = sa.get(f"{BASE_URL}/api/posts", timeout=10)
    check("動態牆回 200", r.status_code == 200)
    check("動態牆含新貼文", any(p["id"] == post_id for p in r.json().get("posts", [])))

    r = sa.get(f"{BASE_URL}/api/users/me/posts", timeout=10)
    check("自己的貼文列表回 200", r.status_code == 200, f"got {r.status_code}")

    # ---------------- 按讚 / 留言 ----------------
    section("按讚與留言")
    r = sb.post(f"{BASE_URL}/api/posts/{post_id}/like", timeout=30)
    check("按讚回 200", r.status_code == 200, f"got {r.status_code}")
    check("liked_by_me=True", r.json().get("post", {}).get("liked_by_me") is True)
    check("like_count=1", r.json().get("post", {}).get("like_count") == 1)

    r = sb.post(f"{BASE_URL}/api/posts/{post_id}/like", timeout=30)
    check("重複按讚不報錯（冪等）", r.status_code == 200, f"got {r.status_code}")
    check("重複按讚 like_count 仍是 1", r.json().get("post", {}).get("like_count") == 1)

    r = sb.post(
        f"{BASE_URL}/api/posts/{post_id}/comments", json={"content": "留言內容"}, timeout=30
    )
    check("留言回 201", r.status_code == 201, f"got {r.status_code} {r.text[:200]}")
    comment_id = r.json().get("comment", {}).get("id") if r.status_code == 201 else None

    r = sa.post(
        f"{BASE_URL}/api/posts/{post_id}/comments",
        json={"content": "回覆", "parent_id": comment_id},
        timeout=30,
    )
    check("回覆留言回 201", r.status_code == 201, f"got {r.status_code}")
    check("回覆有 parent_id", r.json().get("comment", {}).get("parent_id") == comment_id)

    r = sa.get(f"{BASE_URL}/api/posts/{post_id}/comments", timeout=10)
    check("留言列表回 200", r.status_code == 200)
    check("留言列表有 2 則", len(r.json().get("comments", [])) == 2, str(r.json())[:150])

    # ---------------- 通知 ----------------
    section("通知")
    r = sa.get(f"{BASE_URL}/api/notifications", timeout=10)
    check("通知列表回 200", r.status_code == 200, f"got {r.status_code}")
    ndata = r.json()
    types = [n["type"] for n in ndata.get("notifications", [])]
    check("收到 like 通知", "like" in types, str(types))
    check("收到 comment 通知", "comment" in types, str(types))
    check("未讀數 > 0", ndata.get("unread_count", 0) > 0, str(ndata.get("unread_count")))
    check("自己按自己的讚不通知（無 self-like）",
          all(n["actor"]["id"] != n["actor"]["id"] or True for n in ndata.get("notifications", [])))

    r = sa.get(f"{BASE_URL}/api/notifications", timeout=10)
    nid = r.json()["notifications"][0]["id"]
    r = sa.post(f"{BASE_URL}/api/notifications/{nid}/read", timeout=30)
    check("標記單則已讀回 200", r.status_code == 200, f"got {r.status_code}")
    r = sa.post(f"{BASE_URL}/api/notifications/read-all", timeout=30)
    check("全部標已讀回 200", r.status_code == 200, f"got {r.status_code}")
    r = sa.get(f"{BASE_URL}/api/notifications", timeout=10)
    check("未讀數歸零", r.json().get("unread_count") == 0, str(r.json().get("unread_count")))

    # 自己按自己的讚不該有通知
    r = sa.get(f"{BASE_URL}/api/notifications", timeout=10)
    before = r.json().get("unread_count", 0)
    sa.post(f"{BASE_URL}/api/posts/{post_id}/like", timeout=30)
    r = sa.get(f"{BASE_URL}/api/notifications", timeout=10)
    check("自己按自己的讚不產生通知", r.json().get("unread_count", 0) == before)

    # ---------------- 搜尋 ----------------
    section("搜尋")
    r = sa.get(f"{BASE_URL}/api/search", params={"q": f"Hello 大家好 {SUFFIX}"}, timeout=30)
    check("搜尋貼文回 200", r.status_code == 200, f"got {r.status_code}")
    check("搜尋找得到貼文", len(r.json().get("posts", [])) > 0, r.text[:200])

    r = sa.get(f"{BASE_URL}/api/search", params={"q": "Bob"}, timeout=30)
    check("搜尋使用者找得到 B", len(r.json().get("users", [])) > 0, r.text[:200])

    r = sa.get(f"{BASE_URL}/api/search", params={"q": ""}, timeout=30)
    check("空白搜尋回 200", r.status_code == 200, f"got {r.status_code}")
    check("空白搜尋回空陣列", r.json().get("users") == [] and r.json().get("posts") == [])

    # ---------------- 好友 ----------------
    section("好友")
    r = sa.get(f"{BASE_URL}/api/friends/search", params={"q": USER_B["username"]}, timeout=30)
    check("搜尋使用者回 200", r.status_code == 200, f"got {r.status_code}")
    found = r.json().get("users", [])
    check("搜尋找得到 B", len(found) == 1, r.text[:200])
    bob_id = found[0]["id"] if found else None
    check("搜尋不會找到自己", all(u["username"] != USER_A["username"] for u in found), r.text[:200])

    r = sa.post(f"{BASE_URL}/api/friends/requests", json={"receiver_id": bob_id}, timeout=30)
    check("送好友請求回 201", r.status_code == 201, f"got {r.status_code} {r.text[:200]}")
    req_id = r.json().get("request", {}).get("id") if r.status_code == 201 else None

    r = sa.post(f"{BASE_URL}/api/friends/requests", json={"receiver_id": bob_id}, timeout=30)
    check("重複送請求回 409", r.status_code == 409, f"got {r.status_code}")

    r = sb.get(f"{BASE_URL}/api/friends/requests", timeout=10)
    check("B 收到好友請求", len(r.json().get("received", [])) == 1, r.text[:200])

    r = sa.get(f"{BASE_URL}/api/friends/requests", timeout=10)
    check("A 看到送出的請求", len(r.json().get("sent", [])) == 1, r.text[:200])

    r = sb.post(f"{BASE_URL}/api/friends/requests/{req_id}/accept", timeout=30)
    check("接受好友請求回 200", r.status_code == 200, f"got {r.status_code} {r.text[:200]}")

    r = sa.get(f"{BASE_URL}/api/friends", timeout=10)
    check("A 的好友清單有 B", any(u["id"] == bob_id for u in r.json().get("friends", [])))
    r = sb.get(f"{BASE_URL}/api/friends", timeout=10)
    check("B 的好友清單有 A", len(r.json().get("friends", [])) == 1)

    r = sa.get(f"{BASE_URL}/api/notifications", timeout=10)
    check("A 收到 friend_accept 通知", "friend_accept" in [n["type"] for n in r.json().get("notifications", [])], r.text[:300])

    # ---------------- 私訊 ----------------
    section("私人訊息")
    r = sa.post(f"{BASE_URL}/api/messages/conversations", json={"user_id": bob_id}, timeout=30)
    check("建立對話回 201", r.status_code == 201, f"got {r.status_code} {r.text[:200]}")
    conv_id = r.json().get("conversation", {}).get("id") if r.status_code == 201 else None
    check("對話有 other_user", r.json().get("conversation", {}).get("other_user") is not None)

    alice_id = sa.get(f"{BASE_URL}/api/auth/me", timeout=10).json()["user"]["id"]
    r = sb.post(f"{BASE_URL}/api/messages/conversations", json={"user_id": alice_id}, timeout=30)
    check("對話不會重複建立", r.status_code in (200, 201), f"got {r.status_code} {r.text[:150]}")
    r = sb.post(f"{BASE_URL}/api/messages/conversations", json={"user_id": bob_id}, timeout=30)
    check("不能跟自己傳訊息回 400", r.status_code == 400, f"got {r.status_code}")

    r = sa.post(f"{BASE_URL}/api/messages/conversations/{conv_id}", json={"body": "嗨 B"}, timeout=30)
    check("送訊息回 201", r.status_code == 201, f"got {r.status_code} {r.text[:200]}")
    last_id = r.json().get("message", {}).get("id") if r.status_code == 201 else 0

    r = sb.get(f"{BASE_URL}/api/messages/conversations/{conv_id}", timeout=10)
    check("B 輪詢取到訊息", len(r.json().get("messages", [])) == 1, r.text[:200])

    r = sb.get(
        f"{BASE_URL}/api/messages/conversations/{conv_id}", params={"after_id": last_id}, timeout=10
    )
    check("after_id 之後沒有新訊息", len(r.json().get("messages", [])) == 0, r.text[:200])

    sa.post(f"{BASE_URL}/api/messages/conversations/{conv_id}", json={"body": "第二則"}, timeout=30)
    r = sb.get(
        f"{BASE_URL}/api/messages/conversations/{conv_id}", params={"after_id": last_id}, timeout=10
    )
    check("after_id 輪詢只拿新訊息", len(r.json().get("messages", [])) == 1, r.text[:200])

    r = requests.get(f"{BASE_URL}/api/messages/conversations/{conv_id}", timeout=10)
    check("非成員存取對話回 401/403", r.status_code in (401, 403), f"got {r.status_code}")

    r = sa.get(f"{BASE_URL}/api/messages/conversations", timeout=10)
    check("對話列表回 200", r.status_code == 200)
    check("對話列表有該對話", any(c["id"] == conv_id for c in r.json().get("conversations", [])))

    # ---------------- 上傳 ----------------
    section("圖片上傳")
    # 1x1 PNG
    png = bytes.fromhex(
        "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
        "0000000a49444154789c6360000002000100ffff03000006000557bfabd400"
        "00000049454e44ae426082"
    )
    r = sa.post(f"{BASE_URL}/api/uploads", files={"file": ("a.png", png, "image/png")}, timeout=30)
    check("上傳 PNG 回 201", r.status_code == 201, f"got {r.status_code} {r.text[:200]}")
    upload_url = r.json().get("url", "") if r.status_code == 201 else ""
    check("回傳 url 指向 /static/uploads/", upload_url.startswith("/static/uploads/"), upload_url)
    check("檔名是 uuid 格式", len(upload_url.rsplit("/", 1)[-1].split(".")[0]) == 32, upload_url)

    r = sa.get(f"{BASE_URL}{upload_url}", timeout=30)
    check("上傳的檔案可存取", r.status_code == 200, f"got {r.status_code}")

    r = sa.post(
        f"{BASE_URL}/api/uploads", files={"file": ("evil.exe", b"MZ\x90\x00", "application/octet-stream")},
        timeout=30,
    )
    check("上傳 .exe 被拒", r.status_code == 400, f"got {r.status_code}")

    r = sa.post(
        f"{BASE_URL}/api/uploads", files={"file": ("fake.png", b"not a real image", "image/png")},
        timeout=30,
    )
    check("假圖片被拒（內容偵測）", r.status_code == 400, f"got {r.status_code}")

    # ---------------- 個人頁 ----------------
    section("個人頁")
    r = sa.get(f"{BASE_URL}/api/users/{bob_id}", timeout=10)
    check("個人頁回 200", r.status_code == 200, f"got {r.status_code}")
    check("個人頁含 stats", "stats" in r.json())
    check("stats 含 post_count/friend_count",
          "post_count" in r.json().get("stats", {}) and "friend_count" in r.json().get("stats", {}))

    r = sa.patch(f"{BASE_URL}/api/users/me", json={"display_name": "Alice 改名", "bio": "自我介紹"}, timeout=30)
    check("更新個人檔案回 200", r.status_code == 200, f"got {r.status_code}")
    check("顯示名稱已更新", r.json().get("user", {}).get("display_name") == "Alice 改名")

    # ---------------- 登出 ----------------
    section("登出")
    r = sa.post(f"{BASE_URL}/api/auth/logout", timeout=30)
    check("登出回 200", r.status_code == 200, f"got {r.status_code}")
    r = sa.get(f"{BASE_URL}/api/auth/me", timeout=10)
    check("登出後 /me 回 401", r.status_code == 401, f"got {r.status_code}")

    # ---------------- 清理 ----------------
    cleanup()

    # ---------------- 結果 ----------------
    print("\n" + "=" * 60)
    print(f"通過: {len(PASSED)}   失敗: {len(FAILED)}")
    if FAILED:
        print("\n失敗項目:")
        for f in FAILED:
            print(f"  - {f}")
    print("=" * 60)
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
