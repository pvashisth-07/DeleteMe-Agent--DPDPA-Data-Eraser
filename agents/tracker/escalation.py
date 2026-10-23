from datetime import datetime
from typing import Any, Dict, List, Optional

from shared.clock import now
from shared.config import get_law_config
from shared.models import EmailDraft, EscalationDraft


def generate_followup_draft(
    company_name: str,
    user_name: str,
    ticket_id: Optional[str] = None,
    original_date: Optional[str] = None,
) -> EmailDraft:
    """
    Generates a formal follow-up notice when standard 30-day response window is overdue.
    """
    law_cfg = get_law_config()
    template = law_cfg.get("templates", {}).get("followup", "")
    deadline_days = law_cfg.get("RESPONSE_DEADLINE_DAYS", 30)
    disclaimer = law_cfg.get("disclaimer", "This is general information, not legal advice.")
    ref = ticket_id or "PENDING"
    orig = original_date or "30 days prior"

    body = template.format(
        ticket_id=ref,
        company_name=company_name,
        user_name=user_name,
        original_date=orig,
        response_deadline_days=deadline_days,
        disclaimer=disclaimer,
    ).strip()

    subject = f"FOLLOW-UP: Overdue Erasure Request [Ref: {ref}] - {company_name} - {user_name}"
    return EmailDraft(subject=subject, body=body)


def generate_escalation_draft(
    company_name: str,
    user_name: str,
    user_email: str,
    fiduciary_contact: str,
    sent_at: str,
    followup_at: str,
    days_elapsed: int = 60,
    ticket_id: Optional[str] = None,
    correspondence_events: Optional[List[Dict[str, Any]]] = None,
) -> EscalationDraft:
    """
    Generates a formal escalation complaint draft for the Data Protection Board of India under Section 13(3).
    CRITICAL INVARIANTS:
    - Never auto-file (only draft for user review).
    - Never state a Board fee.
    - Explicitly include statutory disclaimer.
    - Cite exhaustion of grievance redressal under Section 13(3).
    """
    law_cfg = get_law_config()
    template = law_cfg.get("templates", {}).get("escalation", "")
    disclaimer = law_cfg.get("disclaimer", "This is general information, not legal advice.")
    ref = ticket_id or "DPDP-GRIEVANCE-EXHAUSTED"
    escalation_date = now().strftime("%Y-%m-%d")

    # Format correspondence log
    corr_lines = []
    if correspondence_events:
        for ev in correspondence_events:
            ts = ev.get("timestamp", "")[:10]
            action = ev.get("reason") or ev.get("to_state")
            corr_lines.append(f"- [{ts}] {action}")
    else:
        corr_lines.append(f"- [{sent_at[:10]}] Initial Erasure Notice dispatched to {fiduciary_contact}")
        corr_lines.append(f"- [{followup_at[:10]}] Statutory Follow-up Notice sent after 30 days of inactivity")
        corr_lines.append(f"- [{escalation_date}] Grievance redressal period expired with no substantive resolution")

    correspondence_log = "\n".join(corr_lines)

    body = template.format(
        company_name=company_name,
        user_name=user_name,
        user_email=user_email,
        fiduciary_contact=fiduciary_contact,
        sent_at=sent_at[:10] if sent_at else "N/A",
        followup_at=followup_at[:10] if followup_at else "N/A",
        days_elapsed=days_elapsed,
        ticket_id=ref,
        correspondence_log=correspondence_log,
        escalation_date=escalation_date,
        disclaimer=disclaimer,
    ).strip()

    subject = f"DRAFT Grievance Escalation to Data Protection Board of India - Failure of Grievance Redressal ({company_name})"
    timeline = [
        f"Initial Request Sent: {sent_at[:10] if sent_at else 'Day 0'}",
        f"Statutory 30-Day Follow-Up Sent: {followup_at[:10] if followup_at else 'Day 30'}",
        f"Grievance Exhaustion Reached: Day {days_elapsed}",
    ]
    relief_sought = [
        f"Direct {company_name} to immediately erase all personal data under Section 12, DPDPA 2023.",
        "Direct Data Fiduciary to provide complete written accounting of any records claimed under statutory exemptions.",
        "Issue appropriate directions under the Digital Personal Data Protection Act, 2023.",
    ]

    return EscalationDraft(
        subject=subject,
        timeline=timeline,
        relief_sought=relief_sought,
        body=body,
    )
