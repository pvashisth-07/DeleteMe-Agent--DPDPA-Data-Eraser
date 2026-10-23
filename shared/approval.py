import hashlib
import hmac
import json
from typing import Any, Dict, List, Optional, Tuple

from shared.config import get_settings


def canonicalize_drafts(drafts: List[Dict[str, Any]]) -> str:
    """Produces canonical deterministic JSON string from list of drafts."""
    sorted_items = []
    for d in sorted(drafts, key=lambda x: str(x.get("company_name", "")).lower()):
        sorted_items.append({
            "company_name": d.get("company_name"),
            "recipient_email": d.get("recipient_email"),
            "subject": d.get("subject"),
            "body": d.get("body"),
            "content_hash": d.get("content_hash"),
        })
    return json.dumps(sorted_items, sort_keys=True)


def compute_drafts_content_hash(drafts: List[Dict[str, Any]]) -> str:
    canonical = canonicalize_drafts(drafts)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def generate_approval_token(
    batch_id: str,
    session_id: str,
    content_hash: str,
    secret: Optional[str] = None,
) -> str:
    """Generates an HMAC-SHA256 signature binding batch_id, session_id, and content_hash."""
    sec = secret or get_settings().APPROVAL_HMAC_SECRET
    payload = f"{batch_id}:{session_id}:{content_hash}".encode("utf-8")
    return hmac.new(sec.encode("utf-8"), payload, hashlib.sha256).hexdigest()


def verify_approval_token(
    token: str,
    batch_id: str,
    session_id: str,
    drafts: List[Dict[str, Any]],
    secret: Optional[str] = None,
) -> Tuple[bool, str]:
    """
    Verifies that the approval token matches the current batch, session, and content hash.
    Rejects tampered drafts, cross-session reuse, or stale tokens after edits.
    """
    if not token or not token.strip():
        return False, "Approval token missing or empty."

    current_hash = compute_drafts_content_hash(drafts)
    sec = secret or get_settings().APPROVAL_HMAC_SECRET
    expected_token = generate_approval_token(batch_id, session_id, current_hash, secret=sec)

    if not hmac.compare_digest(token, expected_token):
        return False, "Invalid approval token: content hash mismatch or token tampered."

    return True, ""
