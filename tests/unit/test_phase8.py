import email
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import json
import pytest

from agents.concierge.cards import (
    build_confirmation_card,
    build_reply_card,
    build_review_card,
    build_status_card,
)
from agents.tracker.imap_poller import (
    extract_request_id_from_recipient,
    parse_raw_email,
)
from shared.db import SqliteRepo
from shared.logging import TraceCollector


# ==============================================================================
# 1. Interactive Cards Metadata String Invariant Tests
# ==============================================================================

def test_cards_metadata_values_are_strictly_strings():
    """
    CRITICAL ACP INVARIANT:
    MetadataContent(type="metadata", metadata=...) strictly requires all dict values
    to be strings (dict[str, str]). Card payload MUST be json.dumps string.
    """
    status_card = build_status_card([
        {
            "company_name": "Swiggy",
            "state": "RESOLVED",
            "ticket_id": "SWIGGY-101",
            "deadline_at": "2026-11-23",
            "sent_at": "2026-10-23",
            "verified": True,
            "payment_status": "Paid",
        }
    ])
    for k, v in status_card.items():
        assert isinstance(k, str)
        assert isinstance(v, str), f"Card metadata value for {k} is not str: {type(v)}"

    # Check payload is valid JSON and contains required fields
    payload = json.loads(status_card["card_payload"])
    assert payload["title"] == "Active DPDPA Erasure Requests"
    assert len(payload["requests"]) == 1
    assert payload["requests"][0]["company"] == "Swiggy"
    assert payload["requests"][0]["verified"] == "VERIFIED"
    assert payload["requests"][0]["payment"] == "Paid"


def test_reply_card_payload_structure():
    card = build_reply_card(
        company="Zomato",
        label="PARTIAL",
        ticket_id="ZOM-404",
        retained_items=["GST Tax Invoices"],
        explanation="Lawfully retained under Income Tax Act for 7 years.",
    )
    for k, v in card.items():
        assert isinstance(v, str)

    payload = json.loads(card["card_payload"])
    assert payload["classification"] == "PARTIAL"
    assert payload["ticket_id"] == "ZOM-404"
    assert "GST Tax Invoices" in payload["retained_items"]
    assert "Income Tax Act" in payload["explanation"]


# ==============================================================================
# 2. Debug Trace Telemetry Tests
# ==============================================================================

def test_debug_trace_formatting():
    collector = TraceCollector()
    collector.record_agent_call("deleteme_concierge", "agent1qfq66...", "intent_parse", 12.5, "OK")
    collector.record_asi1_call("intent_extraction", "asi1", 45.2, retries=0, success=True)
    collector.record_mcp_call("find_grievance_contact", 20.0, "OK")
    collector.record_payment("agent_user", "agent_concierge", "1000000000000000", "atestfet", "Batch Fee", "ref_123", "CONFIRMED")
    collector.record_registry_lookup("drafter", "env_fallback", "agent1q0su27...")

    trace_str = collector.format_debug_trace()
    assert "=== DEBUG TRACE LOG ===" in trace_str
    assert "[AGENT] deleteme_concierge" in trace_str
    assert "[ASI1] intent_extraction" in trace_str
    assert "[MCP] Tool: find_grievance_contact" in trace_str
    assert "[PAYMENT]" in trace_str
    assert "[REGISTRY] drafter via env_fallback" in trace_str


# ==============================================================================
# 3. IMAP Plus-Address Parser Tests
# ==============================================================================

def test_extract_request_id_from_recipient():
    assert extract_request_id_from_recipient("requests+req_670c9083@deleteme.local") == "req_670c9083"
    assert extract_request_id_from_recipient("Delivered-To: <reply+req_paytm_9921@mydomain.in>") == "req_paytm_9921"
    assert extract_request_id_from_recipient("no-plus-address@example.com") is None
    assert extract_request_id_from_recipient("") is None


def test_parse_raw_email(tmp_path):
    repo = SqliteRepo(str(tmp_path / "imap_test.db"))
    req_id = "req_imap_001"
    repo.save_request(
        request_id=req_id,
        batch_id="batch_01",
        session_id="sess_01",
        company_name="Swiggy",
        recipient_email="grievance@swiggy.in",
        user_email="user@test.in",
        subject="Erasure Notice",
        body="Delete data",
        state="SENT",
        sent_at="2026-10-23T10:00:00",
        deadline_at="2026-11-22T10:00:00",
    )

    # Construct mock MIME email
    msg = MIMEMultipart()
    msg["To"] = f"requests+{req_id}@deleteme.local"
    msg["From"] = "grievance@swiggy.in"
    msg["Subject"] = "Re: Confirmation of Deletion [Ref: SWIGGY-PURGE-99]"
    msg.attach(MIMEText("All personal data has been permanently deleted from our database.", "plain"))
    raw_bytes = msg.as_bytes()

    inbound = parse_raw_email(raw_bytes, repo=repo)
    assert inbound is not None
    assert inbound.request_id == req_id
    assert inbound.company_name == "Swiggy"
    assert "SWIGGY-PURGE-99" in inbound.subject
    assert "permanently deleted" in inbound.body
