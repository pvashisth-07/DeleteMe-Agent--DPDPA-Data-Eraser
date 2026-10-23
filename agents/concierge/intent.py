import re
from typing import Any, Dict, Optional, Tuple

from shared.asi1_client import ASI1Client, FakeASI1
from shared.config import get_settings
from shared.logging import setup_logger
from shared.models import IntentExtraction

logger = setup_logger("concierge_intent")


def parse_deterministic_command(text: str) -> Optional[IntentExtraction]:
    """Checks for explicit command keywords before invoking the LLM."""
    clean = text.strip()
    clean_lower = clean.lower()

    if not clean:
        return IntentExtraction(intent="empty")

    # APPROVE <batch_id> or APPROVE
    m_approve = re.match(r"^approve(?:\s+([a-zA-Z0-9_\-]+))?$", clean, re.IGNORECASE)
    if m_approve:
        batch_id = m_approve.group(1) or ""
        return IntentExtraction(
            intent="approve",
            raw_parameters={"batch_id": batch_id},
        )

    # EDIT <company>: <instruction>
    m_edit = re.match(r"^edit\s+([a-zA-Z0-9\s]+?):\s*(.+)$", clean, re.IGNORECASE)
    if m_edit:
        company = m_edit.group(1).strip().title()
        instruction = m_edit.group(2).strip()
        return IntentExtraction(
            intent="edit",
            companies=[company],
            raw_parameters={"instruction": instruction},
        )

    # REMOVE <company>
    m_remove = re.match(r"^remove\s+([a-zA-Z0-9\s]+)$", clean, re.IGNORECASE)
    if m_remove:
        company = m_remove.group(1).strip().title()
        return IntentExtraction(
            intent="remove",
            companies=[company],
        )

    # CANCEL
    if clean_lower in ["cancel", "stop", "abort"]:
        return IntentExtraction(intent="cancel")

    # STATUS
    if clean_lower in ["status", "check status", "my status"]:
        return IntentExtraction(intent="status")

    # DEBUG
    if clean_lower in ["debug", "show debug", "debug trace"]:
        return IntentExtraction(intent="debug")

    # YES / CONFIRM
    if clean_lower in ["yes", "confirm", "proceed", "yep", "haan"]:
        return IntentExtraction(intent="confirm")

    # Reply from <Company>: <body>
    m_reply = re.match(r"^reply\s+from\s+([a-zA-Z0-9\s]+?):\s*(.+)$", clean, re.IGNORECASE | re.DOTALL)
    if m_reply:
        company = m_reply.group(1).strip().title()
        reply_body = m_reply.group(2).strip()
        return IntentExtraction(
            intent="reply_paste",
            companies=[company],
            raw_parameters={"reply_body": reply_body},
        )

    return None


async def extract_intent(
    text: str,
    client: Optional[Any] = None,
) -> Tuple[IntentExtraction, Optional[str]]:
    """
    Extracts intent, companies, and user identity.
    Returns (IntentExtraction, error_message).
    """
    if not text or not text.strip():
        return IntentExtraction(intent="empty"), None

    # Step 1: Deterministic Command Parsing
    cmd = parse_deterministic_command(text)
    if cmd is not None:
        return cmd, None

    # Step 2: ASI1 LLM Extraction
    settings = get_settings()
    llm = client
    if llm is None:
        if not settings.ASI1_API_KEY or "mock" in settings.ASI1_API_KEY.lower():
            llm = FakeASI1()
        else:
            llm = ASI1Client(
                api_key=settings.ASI1_API_KEY,
                base_url=settings.ASI1_BASE_URL,
                model=settings.ASI1_MODEL,
            )

    messages = [
        {
            "role": "system",
            "content": (
                "You are an intent extraction assistant for a privacy agent in India (DPDPA 2023). "
                "Analyze the user's message and extract: "
                "1. intent: 'delete' (for requesting data deletion / erasure), 'status' (checking progress), "
                "'approve', 'edit', 'remove', 'cancel', 'debug', 'reply_paste', or 'other'. "
                "2. companies: list of Indian consumer app / company names mentioned (e.g., Swiggy, Zomato, Paytm). Deduplicate and capitalize. "
                "3. name: the user's full name if provided. "
                "4. email: the user's email address if provided. "
                "5. phone: the user's phone number if provided (format with +91 if possible). "
                "6. identifiers: any user IDs, account numbers, or handles."
            ),
        },
        {"role": "user", "content": text},
    ]

    try:
        extraction = await llm.complete_json(
            IntentExtraction,
            messages=messages,
            purpose="intent_extraction",
        )
        return extraction, None
    except Exception as e:
        logger.error(f"Failed to extract intent with LLM: {e}")
        return (
            IntentExtraction(intent="other"),
            "I'm having trouble thinking right now, please try again in a moment.",
        )
