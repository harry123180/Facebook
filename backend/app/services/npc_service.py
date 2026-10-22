"""NPC（AI 角色）服務。

用 opencode 當作 LLM 引擎：把使用者的訊息送進 opencode session，
拿回角色的回覆寫進對話。

設計重點：
- **背景 thread 執行**：HTTP 請求立刻回應，前端靠 3 秒輪詢拿到回覆，
  不會卡住發送訊息的操作。
- **每個 NPC 一個 opencode session**：角色能記得聊天脈絡，感覺像真人。
- **第一次才帶 persona**：後續只送使用者訊息，session 本身已有角色設定。
- **Windows 相容**：直接呼叫 opencode.exe（實測 0.2s，比 .cmd 少一層 cmd.exe）。
- **UTF-8 強制**：PowerShell 5.1 預設不是 UTF-8，中文會變成 ????。
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

from flask import current_app

from ..extensions import db
from ..models import Conversation, Message, NpcProfile, Notification, User

logger = logging.getLogger(__name__)

# 專案內給 opencode 跑的目錄：放一個乾淨的設定，避免載入整個工作區的規則與 skill
NPC_WORKDIR = Path(__file__).resolve().parent.parent.parent / "npc"

# opencode 單次回覆的逾時（秒）
DEFAULT_TIMEOUT = 120


class NpcError(Exception):
    """NPC 回覆失敗。"""


# --------------------------------------------------------------------------
# opencode 呼叫排隊
# --------------------------------------------------------------------------
# 為什麼要排隊：
#   1. 同時跑多個 `opencode run` 會各自載入模型，GPU 互相搶資源。
#      實測 3 個並行全部逾時（>120s），改成循序執行只要 ~10s each。
#   2. 回覆的延遲優先於預熱，所以用優先佇列讓回覆插隊。
class _OpenCodeWorker:
    """單一背景 worker，循序執行 opencode 呼叫。"""

    def __init__(self) -> None:
        self._cv = threading.Condition()
        self._queue: list[tuple[int, int, object]] = []
        self._seq = 0
        self._thread: threading.Thread | None = None

    def submit(self, fn, priority: int = 10) -> None:
        with self._cv:
            self._seq += 1
            self._queue.append((priority, self._seq, fn))
            self._queue.sort(key=lambda item: (item[0], item[1]))
            self._cv.notify()
            if self._thread is None or not self._thread.is_alive():
                self._thread = threading.Thread(
                    target=self._run, daemon=True, name="opencode-worker"
                )
                self._thread.start()

    def _run(self) -> None:
        while True:
            with self._cv:
                while not self._queue:
                    self._cv.wait(timeout=30)
                if not self._queue:
                    continue
                _, _, fn = self._queue.pop(0)
            try:
                fn()  # type: ignore[operator]
            except Exception:
                logger.exception("opencode worker 任務失敗")

    @property
    def pending(self) -> int:
        with self._cv:
            return len(self._queue)


_worker = _OpenCodeWorker()

# 優先級：回覆 0、預熱 10
PRIORITY_REPLY = 0
PRIORITY_WARMUP = 10


# --------------------------------------------------------------------------
# 判定
# --------------------------------------------------------------------------
def is_npc(user_id: int) -> bool:
    return db.session.get(NpcProfile, user_id) is not None


def get_profile(user_id: int) -> NpcProfile | None:
    return db.session.get(NpcProfile, user_id)


# --------------------------------------------------------------------------
# 呼叫 opencode
# --------------------------------------------------------------------------
def _opencode_cmd() -> list[str]:
    """找出 opencode 執行檔。

    優先用 npm 套件裡真正的 .exe（bun 編譯），比 .cmd 少一層 cmd.exe 開銷。
    """
    candidates = [
        os.path.expandvars(
            r"%APPDATA%\npm\node_modules\@opencode\cli\bin\opencode.exe"
        ),
    ]
    for c in candidates:
        if os.path.exists(c):
            return [c]

    found = shutil.which("opencode")
    if found:
        return [found]

    raise NpcError(
        "找不到 opencode 執行檔。請確認已安裝：npm i -g @opencode/cli"
    )


def _run_env() -> dict:
    """給 opencode 的環境變數。

    關掉全域 skill 與 CLAUDE.md 的載入：NPC 不需要那些，
    而且載入 ~80 個 skill 會讓每次回覆多花好幾秒。
    """
    env = os.environ.copy()
    env["OPENCODE_DISABLE_CLAUDE_CODE_SKILLS"] = "1"
    env["OPENCODE_DISABLE_CLAUDE_CODE_PROMPT"] = "1"
    env["OPENCODE_DISABLE_AUTOUPDATE"] = "1"
    return env


def run_opencode(
    *,
    session_id: str,
    model: str,
    prompt: str,
    timeout: int = DEFAULT_TIMEOUT,
) -> str:
    """送一則訊息給 opencode，取回回覆文字。

    使用 --format json 拿結構化輸出，解析 type=="text" 的事件。
    """
    cmd = _opencode_cmd() + [
        "run",
        "--session",
        session_id,
        "--model",
        model,
        "--format",
        "json",
        prompt,
    ]

    NPC_WORKDIR.mkdir(parents=True, exist_ok=True)

    creationflags = 0
    if os.name == "nt":
        # 不要跳出黑色 console 視窗
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            cwd=str(NPC_WORKDIR),
            env=_run_env(),
            creationflags=creationflags,
        )
    except subprocess.TimeoutExpired as exc:
        raise NpcError(f"opencode 回覆逾時（{timeout}s）") from exc
    except OSError as exc:
        raise NpcError(f"無法啟動 opencode：{exc}") from exc

    if proc.returncode != 0 and not proc.stdout.strip():
        stderr = (proc.stderr or "").strip()[:400]
        logger.error("opencode 失敗 rc=%s stderr=%s", proc.returncode, stderr)
        raise NpcError(f"opencode 執行失敗：{stderr or proc.returncode}")

    text = _extract_text(proc.stdout)
    if not text:
        stderr = (proc.stderr or "").strip()[:300]
        logger.warning("opencode 沒有回傳文字，stderr=%s", stderr)
        raise NpcError("opencode 沒有回傳任何文字")
    return text


def _extract_text(stdout: str) -> str:
    """從 --format json 的輸出中取出回覆文字。

    每一行是一個 JSON event，文字在 {"type":"text","part":{"text":"..."}}。
    """
    chunks: list[str] = []
    for line in (stdout or "").splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if obj.get("type") != "text":
            continue
        part = obj.get("part") or {}
        text = part.get("text")
        if isinstance(text, str) and text.strip():
            chunks.append(text.strip())
    return "\n".join(chunks).strip()


# --------------------------------------------------------------------------
# 產生回覆
# --------------------------------------------------------------------------
def _build_prompt(persona: str, user_message: str) -> str:
    """把角色設定和使用者訊息組成 prompt。

    重點：persona 一定要用「[系統設定]」標記，不然模型會以為那是使用者說的話，
    進而講出「我幫你設定的角色」這種奇怪的話。
    """
    return (
        "[系統設定] 你現在要扮演以下角色，請完全以這個角色的身分、語氣回應。"
        "這是系統設定，不是使用者說的話，絕對不要在回覆中提到它。\n\n"
        f"{persona}\n\n"
        f"[使用者訊息] {user_message}"
    )


def _warmup_prompt(persona: str) -> str:
    return _build_prompt(
        persona,
        "（系統初始化，請用一句話自然地跟你想認識的人打招呼，"
        "不要提及這則初始化訊息。）",
    )


def generate_reply(profile: NpcProfile, user_message: str) -> str:
    """讓 NPC 回一句。會在需要時建立 opencode session。"""
    model = profile.model
    timeout = current_app.config.get("NPC_TIMEOUT", DEFAULT_TIMEOUT)

    first_turn = not profile.session_id
    session_id = profile.session_id or f"ses_npc_{uuid.uuid4().hex[:16]}"

    if first_turn:
        prompt = _build_prompt(profile.persona, user_message)
    else:
        prompt = user_message

    try:
        text = run_opencode(
            session_id=session_id, model=model, prompt=prompt, timeout=timeout
        )
    except NpcError:
        if first_turn:
            raise
        # session 可能已經失效（例如被 opencode 清除），重開一個新的並帶上角色設定
        logger.warning("NPC session %s 失效，重建 session", session_id)
        session_id = f"ses_npc_{uuid.uuid4().hex[:16]}"
        text = run_opencode(
            session_id=session_id,
            model=model,
            prompt=_build_prompt(profile.persona, user_message),
            timeout=timeout,
        )

    profile.session_id = session_id
    db.session.commit()
    return text


# --------------------------------------------------------------------------
# 背景回覆
# --------------------------------------------------------------------------
def spawn_reply(app, *, conversation_id: int, npc_user_id: int, user_message: str) -> None:
    """在背景 thread 產生 NPC 回覆並寫入對話。

    呼叫端（HTTP handler）不會被阻塞；前端靠既有的 3 秒輪詢取得回覆。
    實際的 opencode 呼叫交給 _worker 序列化執行，避免多個呼叫同時搶 GPU。
    """

    def task() -> None:
        with app.app_context():
            text = ""
            try:
                profile = get_profile(npc_user_id)
                if profile is None:
                    raise NpcError("找不到 NPC 設定")
                text = generate_reply(profile, user_message)
            except Exception as exc:  # 任何失敗都要讓使用者看到，而不是靜默
                logger.exception("NPC 回覆失敗")
                text = f"（嗚…我剛剛走神了，{exc}）"

            try:
                _insert_npc_message(conversation_id, npc_user_id, text)
            except Exception:
                logger.exception("NPC 回覆寫入失敗")

    _worker.submit(task, priority=PRIORITY_REPLY)


def spawn_warmup(app, npc_user_id: int) -> None:
    """預熱 NPC 的 opencode session。

    建立 session 本身要 30 秒以上（模型載進 VRAM + opencode 初始化），
    如果等到使用者第一次傳訊息才建立，會讓第一則回覆慢到不可用。
    所以在 NPC 建立時就先在背景跑一次，讓 session 處於熱身完成的狀態。
    """
    if not current_app.config.get("NPC_WARMUP", True):
        return

    def task() -> None:
        with app.app_context():
            profile = get_profile(npc_user_id)
            if profile is None:
                return
            try:
                session_id = profile.session_id or f"ses_npc_{uuid.uuid4().hex[:16]}"
                timeout = current_app.config.get("NPC_WARMUP_TIMEOUT", 300)
                run_opencode(
                    session_id=session_id,
                    model=profile.model,
                    prompt=_warmup_prompt(profile.persona),
                    timeout=timeout,
                )
                profile.session_id = session_id
                db.session.commit()
                logger.info("NPC %s 預熱完成，session=%s", npc_user_id, session_id)
            except Exception:
                logger.exception("NPC %s 預熱失敗（不影響正常使用）", npc_user_id)

    _worker.submit(task, priority=PRIORITY_WARMUP)


def _insert_npc_message(conversation_id: int, npc_user_id: int, text: str) -> None:
    """把 NPC 的回覆寫進對話，並更新最後訊息時間、給對方加通知。"""
    conv = db.session.get(Conversation, conversation_id)
    if conv is None:
        return

    now = datetime.now(timezone.utc)
    message = Message(
        conversation_id=conversation_id,
        sender_id=npc_user_id,
        body=text[:5000],
        created_at=now,
    )
    db.session.add(message)
    conv.last_message_at = now

    # 通知對話裡的其他人
    from sqlalchemy import select

    from ..models import ConversationMember

    others = db.session.execute(
        select(ConversationMember.user_id).where(
            ConversationMember.conversation_id == conversation_id,
            ConversationMember.user_id != npc_user_id,
        )
    ).scalars().all()

    for other_id in others:
        db.session.add(
            Notification(
                user_id=other_id,
                actor_id=npc_user_id,
                type="message",
                target_type="conversation",
                target_id=conversation_id,
            )
        )

    db.session.commit()
