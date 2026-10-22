"""實測 Resend 到底能寄到哪些位址。

用真實的 resend_service 走一遍，看各種收件人的結果。
"""
import os, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
    if "=" in line and not line.strip().startswith("#"):
        k, v = line.split("=", 1)
        os.environ.setdefault(k, v)
os.environ["EMAIL_BACKEND"] = "resend"   # 強制走真實寄信

sys.path.insert(0, str(ROOT / "backend"))
from app import create_app
from app.services.resend_service import EmailSendError, send_verification_code

app = create_app()

CANDIDATES = [
    ("Resend 測試信箱", "onboarding@resend.dev"),
    ("Resend 交付測試", "delivered@resend.dev"),
    ("Resend 退信測試", "bounce@resend.dev"),
    ("常見外部網域", "someone@gmail.com"),
    ("example.com", "test@example.com"),
]

print(f"寄件者: {app.config['RESEND_FROM_EMAIL']}")
print(f"EMAIL_BACKEND: {app.config['EMAIL_BACKEND']}")
print("-" * 70)

for label, addr in CANDIDATES:
    with app.app_context():
        try:
            r = send_verification_code(
                to=addr, display_name="測試", code="123456", ttl_minutes=10
            )
            print(f"  [OK]   {label:<16} {addr:<32} id={r.id}")
        except EmailSendError as e:
            msg = str(e)
            short = "Invalid `to` field (testing mode)" if "Invalid `to` field" in msg else msg[:90]
            print(f"  [FAIL] {label:<16} {addr:<32} {short}")
