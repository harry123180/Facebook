"""驗證 auto 模式：能寄的真的寄，不能寄的自動降級。"""
import os, sys, time, json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
    if "=" in line and not line.strip().startswith("#"):
        k, v = line.split("=", 1)
        os.environ.setdefault(k, v)

sys.path.insert(0, str(ROOT / "backend"))
import requests

BASE = os.getenv("BASE_URL", "http://127.0.0.1:8000")
suf = str(int(time.time()))

CASES = [
    ("帳號本人信箱（應該真寄）", "harry123180@gmail.com", "resend"),
    ("第三方信箱（應該降級）", f"someone{suf}@gmail.com", "console"),
    ("測試信箱（應該真寄）", "onboarding@resend.dev", "resend"),
]

ok = True
for label, email, expect in CASES:
    r = requests.post(
        f"{BASE}/api/auth/register",
        json={
            "email": email,
            "username": f"t{suf[-6:]}{abs(hash(email)) % 1000}",
            "display_name": label,
            "password": "TestPass123!",
        },
        timeout=60,
    )
    print(f"\n--- {label}  ({email}) ---")
    print(f"  HTTP {r.status_code}")
    if r.status_code != 201:
        print("  body:", r.text[:200])
        ok = False
        continue
    d = r.json()
    print(f"  delivery = {d.get('delivery')}   (預期 {expect})")
    print(f"  dev_code = {d.get('dev_code')}")
    print(f"  message  = {d.get('message')}")
    if d.get("delivery") != expect:
        print(f"  ✗ 不符預期")
        ok = False
    else:
        print("  ✓ 符合預期")

print("\n" + "=" * 55)
print("全部符合預期" if ok else "有不符合預期的項目")
sys.exit(0 if ok else 1)
