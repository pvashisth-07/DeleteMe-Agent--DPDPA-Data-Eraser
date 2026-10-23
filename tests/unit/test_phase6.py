import pytest
from agents.dispatcher.agent import handle_dispatch_request
from shared.approval import compute_drafts_content_hash, generate_approval_token
from shared.db import CtxStorageRepo
from shared.models import DispatchRequest
from shared.payments import (
    is_payment_authorized,
    process_inter_agent_micropayment,
    process_user_batch_payment,
)


@pytest.mark.asyncio
async def test_user_batch_payment_bypass_mode():
    repo = CtxStorageRepo()
    ok, ref, label = await process_user_batch_payment(
        repo=repo,
        user_address="user_addr_123",
        concierge_address="concierge_addr_456",
        batch_id="batch_demo_1",
    )
    assert ok is True
    assert ref.startswith("demo_bypass_")
    assert "Demo Mode" in label
    assert "auto-bypassed" in label

    # Check payment recorded in repo
    payment_records = [v for k, v in repo._store.items() if k.startswith("pay:")]
    assert len(payment_records) >= 1
    assert payment_records[0]["status"] == "BYPASSED_DEMO"


@pytest.mark.asyncio
async def test_inter_agent_micropayments():
    repo = CtxStorageRepo()
    tx_disc = await process_inter_agent_micropayment(
        repo=repo,
        payer_address="concierge_addr",
        payee_address="discovery_addr",
        purpose="discovery_lookup_fee",
        reference="req_disc_01",
    )
    assert tx_disc.startswith("micro_")

    tx_track = await process_inter_agent_micropayment(
        repo=repo,
        payer_address="concierge_addr",
        payee_address="tracker_addr",
        purpose="tracking_fee",
        reference="req_track_01",
    )
    assert tx_track.startswith("micro_")

    disc_rec = repo._store.get(f"pay:{tx_disc}")
    assert disc_rec["purpose"] == "discovery_lookup_fee"
    assert disc_rec["status"] == "CONFIRMED"

    track_rec = repo._store.get(f"pay:{tx_track}")
    assert track_rec["purpose"] == "tracking_fee"
    assert track_rec["status"] == "CONFIRMED"


def test_payment_authorization_logic():
    # When bypass is True: always authorized
    assert is_payment_authorized(None, bypass_for_demo=True) is True
    assert is_payment_authorized("ref_123", bypass_for_demo=True) is True

    # When bypass is False: requires valid ref
    assert is_payment_authorized(None, bypass_for_demo=False) is False
    assert is_payment_authorized("", bypass_for_demo=False) is False
    assert is_payment_authorized("REJECT_TEST", bypass_for_demo=False) is False
    assert is_payment_authorized("tx_valid_ref_999", bypass_for_demo=False) is True


@pytest.mark.asyncio
async def test_dispatcher_rejects_unpaid_request_when_not_bypassed(monkeypatch):
    import shared.config
    settings = shared.config.get_settings()
    monkeypatch.setattr(settings, "PAYMENTS_BYPASS_FOR_DEMO", False)

    class MockContext:
        def __init__(self):
            self.replies = []
        async def send(self, recipient, msg):
            self.replies.append(msg)

    ctx = MockContext()
    req = DispatchRequest(
        session_id="sess_1",
        batch_id="batch_1",
        request_id="req_1",
        company_name="Swiggy",
        recipient_email="grievance@swiggy.in",
        subject="Erasure Request",
        body="Body text...",
        approval_token="tok_123",
        content_hash="h1",
        user_email="user@test.com",
        payment_ref=None,  # No payment!
    )

    await handle_dispatch_request(ctx, "concierge_addr", req)
    assert len(ctx.replies) == 1
    assert ctx.replies[0].status == "SEND_FAILED"
    assert "Payment authorization missing" in ctx.replies[0].error
