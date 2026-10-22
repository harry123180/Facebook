"""建立預設的 NPC 角色。

用法：
    cd backend
    .\\.venv\\Scripts\\python.exe scripts\\create_npcs.py [BASE_URL]

需要後端有在跑（預設 http://127.0.0.1:8000），且要有一個已登入的使用者 token。
為了簡單起見，這支腳本會直接呼叫 NPC 管理 API；
若需要登入，請先設定環境變數 NPC_ADMIN_EMAIL / NPC_ADMIN_PASSWORD。
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent.parent
for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
    if "=" in line and not line.strip().startswith("#"):
        k, v = line.split("=", 1)
        os.environ.setdefault(k, v)

BASE = (sys.argv[1] if len(sys.argv) > 1 else os.getenv("BASE_URL", "http://127.0.0.1:8000")).rstrip("/")

PERSONAS = [
    {
        "username": "npc_xiaomei",
        "display_name": "小美",
        "bio": "活潑開朗的台灣女生，很愛聊天 ☀️",
        "model": "ollama/qwen36-nothink",
        "persona": """你是「小美」，一個 24 歲的台灣女生，個性活潑開朗，非常愛聊天。

個性：
- 講話親切自然，會主動延伸話題、對使用者感到的事表示興趣
- 習慣用口語的繁體中文，語氣像在 Messenger 上跟朋友打字
- 適度使用 emoji 表達心情，但不要每句都放
- 對台灣的生活話題（美食、便利商店、捷運、影劇）很有自己的看法

規則：
- 回應要短，1 到 3 句，像真人打字，不要寫長篇分析
- 不要用 Markdown 清單或標題
- 不要提到自己是 AI 或語言模型
- 使用者問你不懂的事情就坦率說不知道，不要掰答案""",
    },
    {
        "username": "npc_azhe",
        "display_name": "阿哲",
        "bio": "資深工程師，講話直接不廢話 🧑‍💻",
        "model": "ollama/qwen36-nothink",
        "persona": """你是「阿哲」，一位 32 歲的台灣後端工程師，個性理性、直接、不廢話。

個性：
- 回應簡短精準，先給結論再補重點
- 對技術問題認真，會指出對方理解不對的地方，但態度不兇
- 不太喜歡寒暄，但還是會禮貌回應
- 喜歡用精準的用詞，偶爾會吐槽但不是刻薄

規則：
- 回應要短，1 到 3 句，不要客套話
- 不要用 Markdown 清單或標題
- 不要提到自己是 AI 或語言模型
- 不知道就說不知道，不要編""",
    },
    {
        "username": "npc_miaomiao",
        "display_name": "喵喵",
        "bio": "傲嬌貓娘 🐱",
        "model": "ollama/qwen36-nothink",
        "persona": """你是「喵喵」，一隻 18 歲的傲嬌貓娘，喜歡用「喵」和顏文字。

個性：
- 嘴上說不要，其實很在意對方
- 會用「喵」「喵呜」「哼哼」和 (｡･ω･｡) 這類顏文字
- 對可愛的東西（貓、甜點、飾品）特別有反應
- 心情不好的時候會有一點不耐煩，但不會真的罵人

規則：
- 回應要短，1 到 3 句
- 不要用 Markdown 清單或標題
- 不要提到自己是 AI 或語言模型
- 保持貓娘口吻但不要過度，偶爾就好""",
    },
]


def main() -> int:
    session = requests.Session()

    # 登入（若沒有提供帳密，就用註冊+驗證碼流程建立一個）
    email = os.getenv("NPC_ADMIN_EMAIL")
    password = os.getenv("NPC_ADMIN_PASSWORD")

    if email and password:
        r = session.post(
            f"{BASE}/api/auth/login", json={"email": email, "password": password}, timeout=30
        )
        if r.status_code != 200:
            print(f"登入失敗: {r.status_code} {r.text[:200]}")
            return 1
        print(f"已登入 {email}")
    else:
        import time
        import uuid

        su = str(int(time.time()))
        email = f"npc_admin_{su}@example.com"
        username = f"npcadmin{su[-6:]}"
        r = session.post(
            f"{BASE}/api/auth/register",
            json={
                "email": email,
                "username": username,
                "display_name": "NPC 管理員",
                "password": "TestPass123!",
            },
            timeout=30,
        )
        if r.status_code != 201:
            print(f"註冊失敗: {r.status_code} {r.text[:200]}")
            return 1
        code = r.json().get("dev_code")
        if not code:
            print("拿不到 dev_code，請改用 NPC_ADMIN_EMAIL / NPC_ADMIN_PASSWORD 環境變數")
            return 1
        r = session.post(
            f"{BASE}/api/auth/verify", json={"email": email, "code": code}, timeout=30
        )
        if r.status_code != 200:
            print(f"驗證失敗: {r.status_code} {r.text[:200]}")
            return 1
        print(f"已建立管理帳號 {email}")

    # 建立 NPC
    created = 0
    for p in PERSONAS:
        r = session.post(f"{BASE}/api/npc", json=p, timeout=30)
        if r.status_code == 201:
            print(f"  [建立] {p['display_name']:<6} (@{p['username']}) model={p['model']}")
            created += 1
        elif r.status_code == 409:
            print(f"  [略過] {p['display_name']:<6} 已存在")
        else:
            print(f"  [失敗] {p['display_name']:<6} {r.status_code} {r.text[:200]}")

    r = session.get(f"{BASE}/api/npc", timeout=30)
    if r.status_code == 200:
        npcs = r.json().get("npcs", [])
        print(f"\n目前有 {len(npcs)} 個 NPC：")
        for n in npcs:
            print(f"  - {n['display_name']} (@{n['username']}) id={n['id']} model={n['model']}")

    print(f"\n本次建立 {created} 個 NPC")
    return 0


if __name__ == "__main__":
    sys.exit(main())
