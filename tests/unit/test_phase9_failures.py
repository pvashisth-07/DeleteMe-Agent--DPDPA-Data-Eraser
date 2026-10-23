import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import AsyncMock, patch
import pytest

from agents.concierge.agent import handle_chat_message
from agents.concierge.intent import extract_intent
from agents.concierge.registry import resolve_agent_address
from agents.concierge.session import ConciergeSession, SessionState, save_session
from agents.dispatcher.agent import dispatcher_agent, handle_dispatch_request
from agents.dispatcher.mailer import send_email
from mcp.tools import validate_no_prohibited_pii
from shared.acp import send_ack
from shared.approval import generate_approval_token
from shared.clock import get_clock, now, now_iso
from shared.config import get_settings
from shared.db import SqliteRepo
from shared.models import DispatchRequest, IntentExtraction
from uagents_core.contrib.protocols.chat import ChatMessage, StartSessionContent, TextContent


@pytest.fixture
def test_repo(tmp_path):
    return SqliteRepo(str(tmp_path / "test_failures.db"))


# ==============================================================================
# 1. Failure Path: Discovery Timeout / Network Failure
# ==============================================================================

@pytest.mark.asyncio
async def test_failure_discovery_network_error(test_repo):
    """
    When specialist discovery fails or times out, the system must not crash;
    it records a partial discovery failure and allows the batch to proceed.
    """
    from agents.concierge.orchestrator import orchestrate_batch_discovery_and_drafting

    sess = ConciergeSession(
        session_id="sess_fail_disc",
        state=SessionState.CONFIRM_COMPANIES,
        companies=["NonExistentUnknownStartup"],
        user_name="Priya Patel",
        user_email="priya@example.in",
    )
    drafts, failures, batch_hash = await orchestrate_batch_discovery_and_drafting(sess, test_repo)

    # Must generate draft with unverified fallback or report partial failure
    assert len(drafts) + len(failures) == 1
    if drafts:
        assert drafts[0]["verified"] is False
    assert batch_hash is not None


# ==============================================================================
# 2. Failure Path: Agentverse Search Failure leads to Env Fallback
# ==============================================================================

@pytest.mark.asyncio
async def test_failure_agentverse_search_fallback():
    """
    When Agentverse registry search fails (e.g. 503 Service Unavailable or network down),
    the system must seamlessly fall back to deterministic addresses from .env.
    """
    with patch("httpx.AsyncClient.get", side_effect=Exception("Agentverse Registry 503")):
        resolved_addr = await resolve_agent_address("discovery")
        settings = get_settings()
        expected = settings.DISCOVERY_ADDR or "agent1qtsk8vqfdywqg89mswxg29dpeftnnxq6jvmp0yphv9z5vcl67fgrjdsdnqg"
        assert resolved_addr == expected


# ==============================================================================
# 3. Failure Path: SMTP Failure leads to SEND_FAILED and Retries
# ==============================================================================

@pytest.mark.asyncio
async def test_failure_smtp_failure_leads_to_send_failed():
    """
    Simulating SMTP transport failure: mailer retries with backoff and returns (False, None, error).
    """
    import smtplib
    with patch("agents.dispatcher.mailer._send_smtp_sync", side_effect=smtplib.SMTPException("SMTP Connection Refused")):
        with patch.object(get_settings(), "SEND_MODE", "live"):
            with patch.object(get_settings(), "CONFIRM_LIVE", True):
                with patch.object(get_settings(), "SMTP_HOST", "smtp.example.com"):
                    success, msg_id, err = await send_email(
                        recipient="privacy@company.com",
                        subject="Erasure Request",
                        body="Body",
                        request_id="req_fail_01",
                        user_email="user@test.in",
                    )
                    assert success is False
                    assert msg_id is None
                    assert "SMTP" in err or "Connection" in err


# ==============================================================================
# 4. Failure Path: Malformed Prompt / Gibberish
# ==============================================================================

@pytest.mark.asyncio
async def test_failure_malformed_prompt():
    """Empty string or non-actionable gibberish should be handled safely."""
    extraction, err = await extract_intent("")
    assert extraction.intent == "empty"

    extraction2, err2 = await extract_intent("!@#$%^&*()_+ ???")
    assert extraction2.intent in {"other", "empty"}


# ==============================================================================
# 5. Failure Path: Session Expiry (User Never Approves)
# ==============================================================================

def test_failure_session_expiry_ttl():
    """Sessions past SESSION_TTL_MINUTES must be flagged as expired."""
    clock = get_clock()
    clock.reset(speed=1.0)

    # Session created 45 minutes in the past
    past_time = now() - timedelta(minutes=45)
    sess1 = ConciergeSession(
        session_id="sess_old_01",
        state=SessionState.AWAITING_APPROVAL,
        updated_at=past_time,
    )
    assert sess1.is_expired(ttl_minutes=30) is True

    # Session updated 5 minutes ago
    recent_time = now() - timedelta(minutes=5)
    sess2 = ConciergeSession(
        session_id="sess_recent_01",
        state=SessionState.AWAITING_APPROVAL,
        updated_at=recent_time,
    )
    assert sess2.is_expired(ttl_minutes=30) is False


# ==============================================================================
# 6. Failure Path: Payment Failure Blocks Dispatch
# ==============================================================================

@pytest.mark.asyncio
async def test_failure_unauthorized_payment_blocks_dispatch(test_repo):
    """
    When PAYMENTS_BYPASS_FOR_DEMO is False and payment_ref is invalid,
    the Dispatcher agent strictly rejects the DispatchRequest.
    """
    class MockSenderCtx:
        def __init__(self):
            self.result = None
        async def send(self, _, res):
            self.result = res

    ctx = MockSenderCtx()
    invalid_disp_req = DispatchRequest(
        session_id="sess_unpaid",
        batch_id="batch_unpaid",
        request_id="req_unpaid_01",
        company_name="Swiggy",
        recipient_email="grievance@swiggy.in",
        subject="Erasure Request",
        body="Delete data",
        approval_token="valid_token",
        content_hash="abc",
        user_email="user@test.in",
        payment_ref="REJECTED_PAYMENT_TX",
    )

    with patch.object(get_settings(), "PAYMENTS_BYPASS_FOR_DEMO", False):
        await handle_dispatch_request(ctx, "concierge_addr", invalid_disp_req)
        assert ctx.result is not None
        assert ctx.result.status == "SEND_FAILED"
        assert "Payment" in ctx.result.error


# ==============================================================================
# 7. Security: PII Safety Guard Enforced
# ==============================================================================

def test_security_pii_safety_guard_blocks_sensitive_data():
    """
    Aadhaar numbers, PAN cards, and passwords must be strictly detected and blocked.
    """
    with pytest.raises(ValueError, match="Aadhaar"):
        validate_no_prohibited_pii("My Aadhaar number is 9876 5432 1098 please delete")

    with pytest.raises(ValueError, match="PAN"):
        validate_no_prohibited_pii("My PAN card is ABCDE1234F please delete")

    with pytest.raises(ValueError, match="credentials/OTP"):
        validate_no_prohibited_pii("My password: SecretPassword123 please delete")
