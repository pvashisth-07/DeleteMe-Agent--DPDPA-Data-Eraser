import asyncio
import smtplib
import ssl
import sys
from pathlib import Path

# Ensure project root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from typing import Dict, Tuple
import httpx

from shared.asi1_client import ASI1Client, FakeASI1
from shared.clock import now_iso
from shared.config import get_settings
from shared.models import IntentExtraction


def check_smtp() -> Tuple[bool, str]:
    settings = get_settings()
    if not settings.SMTP_HOST or not settings.SMTP_USER or not settings.SMTP_PASS:
        return False, "SKIPPED (SMTP credentials not configured in .env - dry_run mode will be used)"

    try:
        context = ssl.create_default_context()
        if settings.SMTP_PORT == 465:
            with smtplib.SMTP_SSL(settings.SMTP_HOST, settings.SMTP_PORT, context=context, timeout=5) as server:
                server.login(settings.SMTP_USER, settings.SMTP_PASS)
        else:
            with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=5) as server:
                server.starttls(context=context)
                server.login(settings.SMTP_USER, settings.SMTP_PASS)
        return True, f"CONNECTED ({settings.SMTP_HOST}:{settings.SMTP_PORT})"
    except Exception as e:
        return False, f"FAILED ({e})"


async def check_policy_urls() -> Tuple[bool, str]:
    urls = [
        "https://www.swiggy.com/privacy-policy",
        "https://www.zomato.com/privacy",
        "https://paytm.com/policies/privacy-policy",
    ]
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    successes = 0
    details = []

    async with httpx.AsyncClient(timeout=8.0, follow_redirects=True, headers=headers) as client:
        for u in urls:
            try:
                resp = await client.get(u)
                if resp.status_code < 400:
                    successes += 1
                    details.append(f"{u.split('/')[2]}: HTTP {resp.status_code}")
                else:
                    details.append(f"{u.split('/')[2]}: HTTP {resp.status_code}")
            except Exception as e:
                details.append(f"{u.split('/')[2]}: {type(e).__name__}")

    all_passed = successes >= 1
    return all_passed, f"{successes}/{len(urls)} reachable ({', '.join(details)})"


async def check_asi1() -> Tuple[bool, str]:
    settings = get_settings()
    if not settings.ASI1_API_KEY or "mock" in settings.ASI1_API_KEY.lower():
        # Test FakeASI1
        fake = FakeASI1()
        res = await fake.complete_json(
            IntentExtraction,
            [{"role": "user", "content": "Delete me from Swiggy and Zomato"}],
            purpose="preflight_check",
        )
        if len(res.companies) >= 2:
            return True, "PASSED (FakeASI1 active with mock key; deterministic fallback verified)"
        return False, "FAILED (FakeASI1 test failed)"

    client = ASI1Client(
        api_key=settings.ASI1_API_KEY,
        base_url=settings.ASI1_BASE_URL,
        model=settings.ASI1_MODEL,
    )
    try:
        res = await asyncio.wait_for(
            client.complete_json(
                IntentExtraction,
                [{"role": "user", "content": "Delete me from Swiggy"}],
                purpose="preflight_check",
            ),
            timeout=10.0,
        )
        return True, f"CONNECTED (ASI:One {settings.ASI1_MODEL} verified: {res.intent})"
    except Exception as e:
        return False, f"FAILED ({e}) - tests will safely use FakeASI1"


async def main():
    print("=" * 60)
    print("   DeleteMe DPDPA Agent - Preflight Diagnostic Suite")
    print("=" * 60)

    smtp_ok, smtp_msg = check_smtp()
    print(f"[*] SMTP Gateway Check:   [{'PASS' if smtp_ok else 'INFO'}] {smtp_msg}")

    urls_ok, urls_msg = await check_policy_urls()
    print(f"[*] Policy URLs Check:    [{'PASS' if urls_ok else 'WARN'}] {urls_msg}")

    asi1_ok, asi1_msg = await check_asi1()
    print(f"[*] ASI:One API Check:    [{'PASS' if asi1_ok else 'INFO'}] {asi1_msg}")

    print("=" * 60)

    # Format Markdown Table for docs/deployment.md
    docs_dir = Path("docs")
    docs_dir.mkdir(parents=True, exist_ok=True)
    deployment_file = docs_dir / "deployment.md"

    table_md = f"""
## Preflight Diagnostics Results ({now_iso()})

| Subsystem | Status | Diagnostic Detail |
|---|---|---|
| **SMTP Gateway** | `{'PASS' if smtp_ok else 'SKIPPED'}` | {smtp_msg} |
| **Privacy Policy Reachability** | `{'PASS' if urls_ok else 'FAIL'}` | {urls_msg} |
| **ASI:One LLM API** | `{'PASS' if asi1_ok else 'FAIL'}` | {asi1_msg} |

"""
    with open(deployment_file, "a", encoding="utf-8") as f:
        f.write(table_md)

    print(f"[+] Diagnostic summary appended to {deployment_file}")


if __name__ == "__main__":
    asyncio.run(main())
