"""端到端測試 NPC 聊天：送訊息 -> 等 opencode 回覆 -> 驗證訊息進了對話。"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent.parent
for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
    if "=" in line and not line.strip().startswith("#"):
        k, v = line.split("=", 1)
        os.environ.setdefault(k, v)

BASE = (sys.argv[1] if len(sys.argv) > 1 else os.getenv("BASE_URL", "http://127.0.0.1:8000")).rstrip("/")
WAIT = int(os.getenv("NPC_WAIT", "150"))

s = requests.Session()
ok = True


def check(label: str, cond: bool, detail: str = "") -> None:
    global ok
    print(f"  [{'PASS' if cond else 'FAIL'}] {label}  {detail}")
    if not cond:
        ok = False


# --- 登入 ---
print("=== 準備帳號 ===")
su = str(int(time.time()))
email = f"npctest_{su}@example.com"
r = s.post(
    f"{BASE}/api/auth/register",
    json={
        "email": email,
        "username": f"npctest{su[-6:]}",
        "display_name": "NPC 測試員",
        "password": "TestPass123!",
    },
    timeout=30,
)
if r.status_code != 201:
    print(f"註冊失敗 {r.status_code} {r.text[:200]}")
    sys.exit(1)
code = r.json().get("dev_code")
r = s.post(f"{BASE}/api/auth/verify", json={"email": email, "code": code}, timeout=30)
check("測試帳號登入", r.status_code == 200, f"email={email}")

# --- 找 NPC ---
print("\n=== 取得 NPC 清單 ===")
r = s.get(f"{BASE}/api/npc", timeout=30)
npcs = r.json().get("npcs", [])
check("有 NPC 可用", len(npcs) > 0, f"{[n['display_name'] for n in npcs]}")
if not npcs:
    sys.exit(1)
npc = npcs[0]
print(f"  使用 NPC: {npc['display_name']} (@{npc['username']}) model={npc['model']}")

# --- 建立對話 ---
print("\n=== 建立對話 ===")
r = s.post(f"{BASE}/api/messages/conversations", json={"user_id": npc["id"]}, timeout=30)
check("建立對話回 201", r.status_code == 201, f"{r.status_code} {r.text[:150]}")
conv_id = r.json()["conversation"]["id"]

# --- 送訊息 ---
print("\n=== 送出訊息 ===")
msg = "嗨！我剛註冊完這個平台，第一次使用聊天功能，你在嗎？"
t0 = time.time()
r = s.post(f"{BASE}/api/messages/conversations/{conv_id}", json={"body": msg}, timeout=30)
check("送訊息回 201", r.status_code == 201, f"{r.status_code} {r.text[:150]}")
check("送訊息很快回應（背景 thread）", time.time() - t0 < 5, f"{time.time()-t0:.2f}s")

# --- 等回覆 ---
print(f"\n=== 等待 NPC 回覆（最多 {WAIT}s，每 3 秒輪詢）===")
reply = None
elapsed = 0
while elapsed < WAIT:
    time.sleep(3)
    elapsed = int(time.time() - t0)
    r = s.get(f"{BASE}/api/messages/conversations/{conv_id}", params={"after_id": 0}, timeout=30)
    msgs = r.json().get("messages", [])
    npc_msgs = [m for m in msgs if m["sender_id"] == npc["id"]]
    if npc_msgs:
        reply = npc_msgs[-1]
        break
    if elapsed % 15 == 0:
        print(f"  ...{elapsed}s 還沒回覆")

check("收到 NPC 回覆", reply is not None, f"等待 {elapsed}s")
if reply:
    print(f"\n  NPC 回覆內容:\n  >>> {reply['body']}\n")
    check("回覆有內容", len(reply["body"].strip()) > 0, f"{len(reply['body'])} 字")
    check("回覆不是錯誤訊息", "嗚" not in reply["body"], reply["body"][:80])
    check("回覆不是 Markdown 清單", not reply["body"].lstrip().startswith(("-", "*", "#")), reply["body"][:40])
    check("回覆在合理長度", len(reply["body"]) < 500, f"{len(reply['body'])} 字")

# --- 續聊（測 session 記憶）---
print("\n=== 續聊（測 opencode session 記憶脈絡）===")
r = s.post(
    f"{BASE}/api/messages/conversations/{conv_id}",
    json={"body": "剛剛我說我第一次用，你還記得嗎？"},
    timeout=30,
)
t1 = time.time()
reply2 = None
while time.time() - t1 < WAIT:
    time.sleep(3)
    r = s.get(f"{BASE}/api/messages/conversations/{conv_id}", params={"after_id": 0}, timeout=30)
    npc_msgs = [m for m in r.json().get("messages", []) if m["sender_id"] == npc["id"]]
    if len(npc_msgs) >= 2:
        reply2 = npc_msgs[-1]
        break
check("收到第二則回覆", reply2 is not None, f"{int(time.time()-t1)}s")
if reply2:
    print(f"  >>> {reply2['body']}\n")
    check("第二則回覆比第一則快（session 已建立）", time.time() - t1 < 25, f"{time.time()-t1:.1f}s")

# --- 未讀數 / 通知 ---
print("\n=== 通知與對話狀態 ===")
r = s.get(f"{BASE}/api/messages/conversations", timeout=30)
convs = r.json().get("conversations", [])
mine = [c for c in convs if c["id"] == conv_id]
check("對話出現在列表", len(mine) == 1, str([c["id"] for c in convs]))
if mine:
    check("對話有 other_user 指向 NPC", mine[0]["other_user"]["id"] == npc["id"], str(mine[0]["other_user"]))
    check("有 last_message", mine[0]["last_message"] is not None)

print("\n" + "=" * 55)
print("全部通過" if ok else "有失敗項目")
sys.exit(0 if ok else 1)
