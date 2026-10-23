import json
from typing import Any, Dict, List, Optional


def build_confirmation_card(
    companies: List[str],
    user_name: str,
    user_email: str,
) -> Dict[str, str]:
    payload = {
        "title": "Confirm DPDPA Erasure Target Companies",
        "subtitle": f"Account Holder: {user_name} ({user_email})",
        "companies": companies,
        "actions": [
            {"label": "Confirm & Draft Notices", "command": "YES", "style": "primary"},
            {"label": "Cancel", "command": "CANCEL", "style": "danger"},
        ],
    }
    return {
        "card_protocol_version": "1",
        "card_kind": "confirmation",
        "requires_card_interaction": "true",
        "card_payload": json.dumps(payload),
    }


def build_review_card(
    batch_id: str,
    send_mode: str,
    drafts: List[Dict[str, Any]],
    failures: Optional[List[Dict[str, str]]] = None,
) -> Dict[str, str]:
    company_items = []
    for d in drafts:
        company_items.append({
            "name": d.get("company_name"),
            "recipient": d.get("recipient_email"),
            "verified": bool(d.get("verified")),
            "subject": d.get("subject"),
            "preview": d.get("body", "")[:250],
            "content_hash": d.get("content_hash", "")[:12],
        })

    payload = {
        "title": "Review DPDPA Section 12 Erasure Requests",
        "batch_id": batch_id,
        "send_mode": send_mode,
        "companies": company_items,
        "partial_failures": failures or [],
        "actions": [
            {"label": f"Approve Batch ({len(drafts)})", "command": f"APPROVE {batch_id}", "style": "primary"},
            {"label": "Cancel Batch", "command": "CANCEL", "style": "danger"},
        ],
    }
    return {
        "card_protocol_version": "1",
        "card_kind": "review",
        "requires_card_interaction": "true",
        "card_payload": json.dumps(payload),
    }


def build_status_card(
    requests: List[Dict[str, Any]],
    payment_status: Optional[str] = None,
) -> Dict[str, str]:
    items = []
    for r in requests:
        verified_flag = bool(r.get("verified", True))
        items.append({
            "company": r.get("company_name"),
            "state": r.get("state"),
            "ticket_id": r.get("ticket_id") or "Pending",
            "deadline": (r.get("deadline_at") or "")[:10],
            "sent_at": (r.get("sent_at") or "")[:10],
            "verified": "VERIFIED" if verified_flag else "UNVERIFIED",
            "payment": r.get("payment_status") or payment_status or "Authorized",
        })

    payload = {
        "title": "Active DPDPA Erasure Requests",
        "requests": items,
        "actions": [
            {"label": "Refresh Status", "command": "STATUS", "style": "secondary"},
            {"label": "View Debug Trace", "command": "DEBUG", "style": "secondary"},
        ],
    }
    return {
        "card_protocol_version": "1",
        "card_kind": "status",
        "requires_card_interaction": "false",
        "card_payload": json.dumps(payload),
    }


def build_reply_card(
    company: str,
    label: str,
    ticket_id: Optional[str],
    retained_items: List[str],
    explanation: str,
) -> Dict[str, str]:
    payload = {
        "title": f"Reply Processed from {company}",
        "classification": label,
        "ticket_id": ticket_id or "N/A",
        "retained_items": retained_items,
        "explanation": explanation,
        "actions": [
            {"label": "View All Status", "command": "STATUS", "style": "primary"},
        ],
    }
    return {
        "card_protocol_version": "1",
        "card_kind": "reply",
        "requires_card_interaction": "false",
        "card_payload": json.dumps(payload),
    }
