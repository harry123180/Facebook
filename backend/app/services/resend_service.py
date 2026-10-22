"""Resend 寄信服務。

注意：目前使用的 RESEND_API_KEY 是 restricted key（僅能送信），
所以這個模組只呼叫 Emails.send，不要加任何讀取 domain / contacts 的呼叫，
否則會拿到 401 restricted_api_key。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import resend
from flask import current_app

logger = logging.getLogger(__name__)


class EmailSendError(Exception):
    """寄信失敗（網路錯誤、Resend 回應錯誤、額度不足…）。"""


@dataclass
class SentMail:
    id: str
    to: str
    #: "resend" = 真的寄出去了；"console" = 降級成印在 log
    mode: str = "resend"


def _client():
    api_key = current_app.config["RESEND_API_KEY"]
    if not api_key:
        raise EmailSendError("RESEND_API_KEY 未設定")
    resend.api_key = api_key
    return resend


def _console_backend() -> bool:
    """console 模式：不寄信，驗證碼直接輸出到伺服器 log。"""
    return current_app.config.get("EMAIL_BACKEND", "auto") == "console"


def _auto_backend() -> bool:
    return current_app.config.get("EMAIL_BACKEND", "auto") == "auto"


def _is_testing_mode_error(message: str) -> bool:
    """判斷錯誤是否來自 Resend 的 testing mode 限制。

    Resend 目前的兩種訊息：
      - "You can only send testing emails to your own email address (...)"
      - "Invalid `to` field. Please use our testing email address instead of domains like ..."
    """
    lowered = message.lower()
    return (
        "testing email" in lowered
        or "invalid `to` field" in lowered
        or "invalid to field" in lowered
    )


def _send(*, to: str, subject: str, html: str, text: str) -> SentMail:
    client = _client()
    params = {
        "from": current_app.config["RESEND_FROM_EMAIL"],
        "to": [to],
        "subject": subject,
        "html": html,
        "text": text,
    }
    try:
        response = client.Emails.send(params)
    except Exception as exc:  # SDK 的例外型別隨版本變動，這裡全攔並轉成自己的例外
        logger.exception("Resend send failed for %s", to)
        raise EmailSendError(str(exc)) from exc

    mail_id = response.get("id") if isinstance(response, dict) else getattr(response, "id", None)
    if not mail_id:
        logger.error("Resend send returned no id: %r", response)
        raise EmailSendError("Resend 未回傳郵件 ID")
    return SentMail(id=mail_id, to=to)


def _console_emit(to: str, code: str, reason: str = "") -> SentMail:
    """把驗證碼印到 log，取代實際寄信。"""
    banner = "=" * 62
    logger.warning(
        "\n%s\nEMAIL_BACKEND=console，未實際寄信%s\n收件者: %s\n驗證碼: %s\n%s",
        banner,
        f"（{reason}）" if reason else "",
        to,
        code,
        banner,
    )
    return SentMail(id=f"console-{code}", to=to, mode="console")


# --------------------------------------------------------------------------
# 驗證碼信
# --------------------------------------------------------------------------
def send_verification_code(*, to: str, display_name: str, code: str, ttl_minutes: int = 10) -> SentMail:
    """寄出 Email 驗證碼。

    EMAIL_BACKEND=auto 時，若 Resend 因 testing mode 擋下這個收件人，
    自動降級成 console（驗證碼印 log + 回傳 dev_code），註冊流程不會卡死。
    """
    safe_name = _escape(display_name)
    safe_code = _escape(code)

    if _console_backend():
        return _console_emit(to, code)

    html = f"""<!doctype html>
<html><body style="margin:0;padding:24px;background:#f0f2f5;font-family:-apple-system,Segoe UI,Roboto,'Helvetica Neue',Arial,'Noto Sans TC',sans-serif;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:520px;margin:0 auto;background:#ffffff;border-radius:12px;overflow:hidden;">
    <tr><td style="background:#1877f2;padding:20px 32px;">
      <span style="color:#ffffff;font-size:22px;font-weight:700;letter-spacing:.5px;">Facebook MVP</span>
    </td></tr>
    <tr><td style="padding:32px;color:#1c1e21;line-height:1.6;">
      <p style="margin:0 0 16px;font-size:16px;">Hi {safe_name}，歡迎加入！</p>
      <p style="margin:0 0 20px;font-size:15px;color:#606770;">請輸入下面的驗證碼完成信箱驗證：</p>
      <div style="margin:0 0 24px;padding:18px;text-align:center;background:#f0f2f5;border-radius:10px;">
        <span style="font-size:34px;font-weight:700;letter-spacing:10px;color:#1877f2;font-family:'SF Mono',Consolas,monospace;">{safe_code}</span>
      </div>
      <p style="margin:0 0 8px;font-size:14px;color:#606770;">驗證碼 <strong>{ttl_minutes} 分鐘</strong>內有效。</p>
      <p style="margin:0 0 24px;font-size:14px;color:#606770;">若不是你自己註冊，忽略這封信即可。</p>
      <p style="margin:0;font-size:13px;color:#8a8d91;">你收到這封信，代表有人用這個信箱註冊了 Facebook MVP 帳號。</p>
    </td></tr>
  </table>
</body></html>"""

    text = (
        f"Hi {display_name}，歡迎加入 Facebook MVP！\n\n"
        f"你的信箱驗證碼是：{code}\n"
        f"驗證碼 {ttl_minutes} 分鐘內有效。\n\n"
        f"若不是你自己註冊，忽略這封信即可。"
    )

    try:
        return _send(
            to=to,
            subject=f"你的 Facebook MVP 驗證碼：{code}",
            html=html,
            text=text,
        )
    except EmailSendError as exc:
        if _auto_backend() and _is_testing_mode_error(str(exc)):
            # Resend 帳號還在 testing mode，只允許寄到帳號本人信箱或測試信箱。
            # 與其讓註冊流程整個失敗，不如降級成 console，把驗證碼交給前端顯示。
            logger.warning(
                "Resend testing mode 擋下收件者 %s，降級為 console 模式：%s", to, exc
            )
            return _console_emit(to, code, reason="Resend testing mode 限制")
        raise


def send_welcome(*, to: str, display_name: str) -> SentMail:
    """驗證成功後的歡迎信。"""
    if _console_backend():
        logger.warning("[EMAIL_BACKEND=console] 略過歡迎信 -> %s", to)
        return SentMail(id=f"console-welcome-{to}", to=to, mode="console")

    safe_name = _escape(display_name)
    html = f"""<!doctype html>
<html><body style="margin:0;padding:24px;background:#f0f2f5;font-family:-apple-system,Segoe UI,Roboto,'Helvetica Neue',Arial,'Noto Sans TC',sans-serif;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:520px;margin:0 auto;background:#ffffff;border-radius:12px;overflow:hidden;">
    <tr><td style="background:#1877f2;padding:20px 32px;">
      <span style="color:#ffffff;font-size:22px;font-weight:700;">Facebook MVP</span>
    </td></tr>
    <tr><td style="padding:32px;color:#1c1e21;line-height:1.6;">
      <p style="margin:0 0 16px;font-size:16px;">信箱驗證完成，{safe_name} 歡迎加入！</p>
      <p style="margin:0;font-size:15px;color:#606770;">現在可以開始發文、加好友、傳訊息了。</p>
    </td></tr>
  </table>
</body></html>"""
    text = f"{display_name}，信箱驗證完成，歡迎加入 Facebook MVP！"
    return _send(to=to, subject="歡迎加入 Facebook MVP", html=html, text=text)


def _escape(value: str) -> str:
    """HTML 逸出，避免使用者名稱注入到寄信內容裡。"""
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
    )
