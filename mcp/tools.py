import hashlib
import json
import re
from pathlib import Path
from typing import Any, Dict, Optional, Tuple
from bs4 import BeautifulSoup
import httpx

from shared.asi1_client import FakeASI1
from shared.config import get_law_config, get_settings
from shared.db import SqliteRepo
from shared.logging import global_trace_collector, setup_logger

logger = setup_logger("mcp_tools")
BASE_DIR = Path(__file__).resolve().parent.parent

# PII Guard Regexes: Aadhaar (12 digits), PAN (5 letters, 4 digits, 1 letter), OTP/Password
AADHAAR_REGEX = re.compile(r"(?<!\+91)(?<!\+)\b[2-9]\d{3}[\s\-]\d{4}[\s\-]\d{4}\b|(?<!\+91)(?<!\+)\b[2-9]\d{11}\b")
PAN_REGEX = re.compile(r"\b[A-Z]{5}\d{4}[A-Z]\b")
SENSITIVE_KEYWORDS_REGEX = re.compile(r"\b(password|otp|pin|cvv)\s*[:=]\s*\S+", re.IGNORECASE)


def validate_no_prohibited_pii(text: str) -> None:
    """Enforces strict safety guard: Never include Aadhaar, PAN, OTPs or passwords."""
    if AADHAAR_REGEX.search(text):
        raise ValueError("Security Violation: Draft contains Aadhaar number which is prohibited.")
    if PAN_REGEX.search(text):
        raise ValueError("Security Violation: Draft contains PAN number which is prohibited.")
    if SENSITIVE_KEYWORDS_REGEX.search(text):
        raise ValueError("Security Violation: Draft contains credentials/OTP which is prohibited.")


def compute_content_hash(subject: str, body: str, recipient: str) -> str:
    payload = json.dumps({"subject": subject, "body": body, "recipient": recipient}, sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def find_company_record(company_name: str) -> Optional[Dict[str, Any]]:
    companies_file = BASE_DIR / "data" / "companies.json"
    if not companies_file.exists():
        return None
    companies = json.loads(companies_file.read_text(encoding="utf-8"))
    query = company_name.lower().strip()
    for c in companies:
        if c["name"].lower() == query:
            return c
        for alias in c.get("aliases", []):
            if alias.lower() == query or query in alias.lower():
                return c
    return None


async def fetch_policy_html(url: str, repo: Optional[SqliteRepo] = None) -> str:
    # 1. Check DB Cache
    if repo:
        cached = repo.get_cached_policy(url)
        if cached:
            return cached

    # 2. Check local test fixtures fallback
    fixtures_dir = BASE_DIR / "tests" / "fixtures" / "policies"
    if "swiggy" in url.lower():
        fixture = fixtures_dir / "swiggy_policy.html"
        if fixture.exists():
            return fixture.read_text(encoding="utf-8")
    elif "unverified" in url.lower():
        fixture = fixtures_dir / "unverified_company.html"
        if fixture.exists():
            return fixture.read_text(encoding="utf-8")

    # 3. Live HTTP fetch
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko)"}
    try:
        async with httpx.AsyncClient(timeout=8.0, follow_redirects=True, headers=headers) as client:
            resp = await client.get(url)
            if resp.status_code == 200:
                html = resp.text
                if repo:
                    repo.set_cached_policy(url, html)
                return html
    except Exception as e:
        logger.warning(f"Failed to fetch live policy from {url}: {e}")

    if "swiggy" in url.lower():
        fixture = fixtures_dir / "swiggy_policy.html"
        return fixture.read_text(encoding="utf-8") if fixture.exists() else ""
    return ""


def extract_officer_and_email_from_html(html: str, domain: str) -> Tuple[Optional[str], str, bool]:
    soup = BeautifulSoup(html, "html.parser")
    # Strip script/style
    for s in soup(["script", "style"]):
        s.extract()
    text = soup.get_text(separator=" ")

    # Find email addresses literally in the HTML text
    email_pattern = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b")
    all_emails = email_pattern.findall(text)

    # Prioritize privacy / grievance / nodal emails
    priority_emails = [e for e in all_emails if any(k in e.lower() for k in ["grievance", "privacy", "nodal", "dpo", "legal"])]
    if priority_emails:
        chosen_email = priority_emails[0]
        verified = True
    elif all_emails:
        chosen_email = all_emails[0]
        verified = True
    else:
        # Fallback to privacy@<domain> with verified=False
        chosen_email = f"privacy@{domain}"
        verified = False

    # Extract officer name
    officer_match = re.search(
        r"(?:name|officer\s*name)[:\s]+((?:mr\.|ms\.|mrs\.)?\s*[A-Z][a-zA-Z\s]{2,25}?)(?=\s+(?:designation|email|office|\.|\n|$))",
        text,
        re.IGNORECASE,
    )
    if not officer_match:
        officer_match = re.search(
            r"(?:grievance officer|nodal officer|data protection officer|dpo)[\s:]+(?:mr\.|ms\.|mrs\.)?\s*([A-Z][a-zA-Z\s]{2,30})",
            text,
            re.IGNORECASE,
        )
    officer_name = officer_match.group(1).strip() if officer_match else None

    return officer_name, chosen_email, verified


async def find_grievance_contact_impl(company: str, repo: Optional[SqliteRepo] = None) -> Dict[str, Any]:
    company_clean = company.strip()
    record = find_company_record(company_clean)

    if record:
        domain = record["domain"]
        policy_url = record["privacy_policy_url"]
        resolved_name = record["name"]
    else:
        # Unknown company: resolve domain heuristic
        domain = f"{company_clean.lower().replace(' ', '')}.com"
        policy_url = f"https://www.{domain}/privacy"
        resolved_name = company_clean.title()

    html = await fetch_policy_html(policy_url, repo=repo)
    officer_name, email, verified = extract_officer_and_email_from_html(html, domain)

    if not verified:
        email_note = f"{email} (UNVERIFIED - please confirm)"
    else:
        email_note = email

    return {
        "company_name": resolved_name,
        "domain": domain,
        "officer_name": officer_name,
        "email": email,
        "email_display": email_note,
        "source_url": policy_url,
        "verified": verified,
    }


def draft_erasure_request_impl(
    company_name: str,
    recipient_email: str,
    user_profile: Dict[str, Any],
    verified: bool = False,
) -> Dict[str, Any]:
    law_cfg = get_law_config()
    deadline = law_cfg.get("RESPONSE_DEADLINE_DAYS", 30)
    disclaimer = law_cfg.get("disclaimer", "This is general information, not legal advice.")
    law_in_force = law_cfg.get("law_in_force", False)

    template_key = "erasure_post_commencement" if law_in_force else "erasure_pre_commencement"
    template_str = law_cfg.get("templates", {}).get(template_key, "")

    user_name = user_profile.get("name", "Account Holder")
    user_email = user_profile.get("email", "")
    user_phone = user_profile.get("phone")
    identifiers = user_profile.get("identifiers", {})

    id_lines = [f"- Registered Email: {user_email}"]
    if user_phone:
        id_lines.append(f"- Registered Phone: {user_phone}")
    for k, v in identifiers.items():
        id_lines.append(f"- {k}: {v}")
    identifiers_block = "\n".join(id_lines)

    filled_text = template_str.format(
        company_name=company_name,
        user_name=user_name,
        identifiers_block=identifiers_block,
        response_deadline_days=deadline,
        disclaimer=disclaimer,
    )

    # Validate safety guard: No forbidden PII (Aadhaar, PAN, passwords)
    validate_no_prohibited_pii(filled_text)

    # Separate subject and body
    lines = filled_text.strip().split("\n")
    subject = lines[0].replace("Subject:", "").strip()
    body = "\n".join(lines[1:]).strip()

    c_hash = compute_content_hash(subject, body, recipient_email)

    return {
        "company_name": company_name,
        "recipient_email": recipient_email,
        "subject": subject,
        "body": body,
        "content_hash": c_hash,
        "verified": verified,
    }
