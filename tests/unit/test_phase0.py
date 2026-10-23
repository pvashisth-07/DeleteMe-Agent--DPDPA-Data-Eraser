import json
import pytest
from pathlib import Path

from shared.asi1_client import FakeASI1
from shared.clock import DemoClock
from shared.config import get_law_config, get_pricing_config, get_settings
from shared.db import CtxStorageRepo, SqliteRepo
from shared.models import (
    ContactExtraction,
    DiscoveryRequest,
    DiscoveryResult,
    DispatchRequest,
    DispatchResult,
    DraftRequest,
    DraftResult,
    EmailDraft,
    EscalationDraft,
    InboundReply,
    IntentExtraction,
    ReplyClassification,
    StatusUpdate,
    UserProfile,
)
from shared.payments import (
    create_payment_request,
    commit_payment,
    is_payment_authorized,
)


def test_models_instantiation_and_serialization():
    profile = UserProfile(
        name="Aarav Sharma",
        email="aarav@example.com",
        phone="+919876543210",
        identifiers={"user_id": "usr_9981"},
    )
    assert profile.name == "Aarav Sharma"
    assert profile.identifiers["user_id"] == "usr_9981"

    disc_req = DiscoveryRequest(
        session_id="sess_1",
        batch_id="batch_1",
        company_name="Swiggy",
        domain="swiggy.in",
    )
    assert disc_req.session_id == "sess_1"

    disc_res = DiscoveryResult(
        session_id="sess_1",
        batch_id="batch_1",
        company_name="Swiggy",
        email="grievance@swiggy.in",
        verified=True,
    )
    assert disc_res.verified is True

    draft_req = DraftRequest(
        session_id="sess_1",
        batch_id="batch_1",
        request_id="req_1",
        company_name="Swiggy",
        recipient_email="grievance@swiggy.in",
        user_profile=profile,
    )
    assert draft_req.request_id == "req_1"

    draft_res = DraftResult(
        session_id="sess_1",
        batch_id="batch_1",
        request_id="req_1",
        company_name="Swiggy",
        recipient_email="grievance@swiggy.in",
        subject="DPDPA Section 12 Erasure Notice",
        body="Body text...",
        content_hash="abc123hash",
        verified=True,
    )
    assert draft_res.content_hash == "abc123hash"

    disp_req = DispatchRequest(
        session_id="sess_1",
        batch_id="batch_1",
        request_id="req_1",
        company_name="Swiggy",
        recipient_email="grievance@swiggy.in",
        subject=draft_res.subject,
        body=draft_res.body,
        approval_token="tok_hmac_123",
        content_hash="abc123hash",
        user_email=profile.email,
    )
    assert disp_req.approval_token == "tok_hmac_123"

    disp_res = DispatchResult(
        session_id="sess_1",
        batch_id="batch_1",
        request_id="req_1",
        company_name="Swiggy",
        status="SENT",
        message_id="<msg_001@deleteme.local>",
        sent_at="2026-10-23T10:00:00Z",
        deadline_at="2026-11-22T10:00:00Z",
    )
    assert disp_res.status == "SENT"

    track_req = StatusUpdate(
        session_id="sess_1",
        batch_id="batch_1",
        request_id="req_1",
        company_name="Swiggy",
        state="ACKNOWLEDGED",
        ticket_id="SWG-9988",
        updated_at="2026-10-23T11:00:00Z",
    )
    assert track_req.ticket_id == "SWG-9988"


def test_sqlite_repository(tmp_path):
    db_file = tmp_path / "test_deleteme.db"
    repo = SqliteRepo(str(db_file))

    # Session
    repo.save_session("s_1", "NEW", user_name="Priya", user_email="priya@example.com")
    sess = repo.get_session("s_1")
    assert sess is not None
    assert sess["user_name"] == "Priya"
    assert sess["state"] == "NEW"

    # Batch
    repo.save_batch("b_1", "s_1", "hash_abc", "DRAFTED")
    batch = repo.get_batch("b_1")
    assert batch is not None
    assert batch["status"] == "DRAFTED"

    # Draft
    repo.save_draft(
        request_id="r_1",
        batch_id="b_1",
        session_id="s_1",
        company_name="Zomato",
        recipient_email="grievance@zomato.com",
        subject="Notice",
        body="Text",
        content_hash="hash_abc",
        verified=True,
    )
    drafts = repo.get_drafts_for_batch("b_1")
    assert len(drafts) == 1
    assert drafts[0]["company_name"] == "Zomato"

    # Request & State Machine Updates
    repo.save_request(
        request_id="r_1",
        batch_id="b_1",
        session_id="s_1",
        company_name="Zomato",
        recipient_email="grievance@zomato.com",
        user_email="priya@example.com",
        subject="Notice",
        body="Text",
        state="SENT",
        sent_at="2026-10-23T00:00:00Z",
        deadline_at="2026-11-22T00:00:00Z",
    )
    req = repo.get_request("r_1")
    assert req["state"] == "SENT"

    repo.update_request_state("r_1", "ACKNOWLEDGED", ticket_id="ZOM-1122", reason="Auto-ack received")
    req_updated = repo.get_request("r_1")
    assert req_updated["state"] == "ACKNOWLEDGED"
    assert req_updated["ticket_id"] == "ZOM-1122"

    events = repo.get_events_for_request("r_1")
    assert len(events) >= 1
    assert events[-1]["to_state"] == "ACKNOWLEDGED"

    open_reqs = repo.get_all_open_requests()
    assert len(open_reqs) == 1

    # Contacts Cache
    repo.set_cached_contact("zomato", "DPO Zomato", "grievance@zomato.com", "Gurgaon", "https://zomato.com", True)
    contact = repo.get_cached_contact("Zomato")
    assert contact is not None
    assert contact["email"] == "grievance@zomato.com"


def test_ctx_storage_repository():
    mem_store = {}
    repo = CtxStorageRepo(mem_store)

    repo.save_session("s_test", "CONFIRM_COMPANIES", "Rohan", "rohan@test.com")
    sess = repo.get_session("s_test")
    assert sess["state"] == "CONFIRM_COMPANIES"
    assert sess["user_name"] == "Rohan"

    repo.save_draft(
        request_id="r_2",
        batch_id="b_2",
        session_id="s_test",
        company_name="Paytm",
        recipient_email="nodal@paytm.com",
        subject="Notice",
        body="Body",
        content_hash="h123",
        verified=False,
    )
    drafts = repo.get_drafts_for_batch("b_2")
    assert len(drafts) == 1
    assert drafts[0]["company_name"] == "Paytm"


def test_clock_acceleration():
    clock = DemoClock(speed=1.0)
    now1 = clock.now()
    assert now1 is not None

    # Accelerated mode: 1 second = 1 day (86400x)
    clock.set_speed(86400.0)
    assert clock.get_speed() == 86400.0
    sec_for_30_days = clock.days_to_seconds(30)
    assert abs(sec_for_30_days - 30.0) < 0.01

    # Advance clock directly
    clock.advance_days(30)
    now2 = clock.now()
    delta_days = (now2 - now1).total_seconds() / 86400.0
    assert delta_days >= 29.9


@pytest.mark.asyncio
async def test_fake_asi1_deterministic_responses():
    fake = FakeASI1()

    # Intent 1: Multi-company deletion
    res1 = await fake.complete_json(
        IntentExtraction,
        [{"role": "user", "content": "Delete me from Swiggy, Zomato and Paytm. My name is Aarav, email aarav@test.com"}],
    )
    assert res1.intent == "delete"
    assert set(res1.companies) == {"Swiggy", "Zomato", "Paytm"}
    assert res1.email == "aarav@test.com"

    # Intent 2: Hinglish deletion
    res2 = await fake.complete_json(
        IntentExtraction,
        [{"role": "user", "content": "mera data delete kardo zomato se please"}],
    )
    assert res2.intent == "delete"
    assert "Zomato" in res2.companies

    # Contact Extraction
    contact = await fake.complete_json(
        ContactExtraction,
        [{"role": "user", "content": "Grievance Officer: Mr. Sharma. Email: privacy@swiggy.in"}],
    )
    assert contact.email == "privacy@swiggy.in"

    # Reply Classification
    reply_ack = await fake.complete_json(
        ReplyClassification,
        [{"role": "user", "content": "We have received your request. Ticket #SWG-5544 opened."}],
    )
    assert reply_ack.label == "ACKNOWLEDGED"
    assert reply_ack.ticket_id == "SWG-5544"

    reply_partial = await fake.complete_json(
        ReplyClassification,
        [{"role": "user", "content": "We deleted your profile, but retained tax invoices for 7 years under Income Tax Act."}],
    )
    assert reply_partial.label == "PARTIAL"
    assert "Tax invoices" in reply_partial.retained_items[0]


def test_config_and_companies():
    settings = get_settings()
    assert settings.SESSION_TTL_MINUTES == 30
    assert settings.SEND_MODE in ("dry_run", "demo_redirect", "live")

    law = get_law_config()
    assert law["RESPONSE_DEADLINE_DAYS"] == 30
    assert law["law_in_force"] is False
    assert "disclaimer" in law
    assert "templates" in law
    assert "erasure_pre_commencement" in law["templates"]

    pricing = get_pricing_config()
    assert pricing["currency"] == "atestfet"
    assert pricing["batch_fee"] == "1000000000000000"

    companies_file = Path("data/companies.json")
    assert companies_file.exists()
    companies = json.loads(companies_file.read_text(encoding="utf-8"))
    assert len(companies) >= 30
    for c in companies:
        assert "name" in c
        assert "domain" in c
        assert "privacy_policy_url" in c
        assert c["contact_email"] is None, f"{c['name']} contact_email should be null per spec"


def test_payment_helpers():
    req = create_payment_request(
        recipient="agent_wallet_xyz",
        amount="1000000000000000",
        reference="batch_1",
    )
    assert req.accepted_funds[0].amount == "1000000000000000"
    assert req.reference == "batch_1"

    commit = commit_payment(
        recipient="agent_wallet_xyz",
        amount="1000000000000000",
        reference="batch_1",
    )
    assert commit.transaction_id.startswith("tx_")

    # Bypass check
    assert is_payment_authorized("tx_123", bypass_for_demo=True) is True
    assert is_payment_authorized(None, bypass_for_demo=False) is False
    assert is_payment_authorized("tx_123", bypass_for_demo=False) is True


@pytest.mark.asyncio
async def test_asi1_json_repair_retry(monkeypatch):
    from unittest.mock import AsyncMock, MagicMock
    from shared.asi1_client import ASI1Client
    from shared.models import IntentExtraction

    client = ASI1Client(api_key="mock", base_url="https://api.asi1.ai/v1", model="asi1")

    # Call 1 returns malformed JSON; Call 2 (repair prompt) returns valid JSON
    mock_resp1 = MagicMock()
    mock_resp1.choices = [MagicMock(message=MagicMock(content="invalid json {"))]

    mock_resp2 = MagicMock()
    mock_resp2.choices = [
        MagicMock(message=MagicMock(content=json.dumps({"intent": "delete", "companies": ["Swiggy"]})))
    ]

    mock_raw = AsyncMock(side_effect=[mock_resp1, mock_resp2])
    monkeypatch.setattr(client, "_raw_chat_completion", mock_raw)

    result = await client.complete_json(
        IntentExtraction,
        [{"role": "user", "content": "Delete me from Swiggy"}],
        purpose="test_repair",
    )

    assert result.intent == "delete"
    assert result.companies == ["Swiggy"]
    assert mock_raw.call_count == 2
