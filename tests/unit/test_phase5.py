import pytest
from agents.dispatcher.mailer import send_email
from shared.approval import compute_drafts_content_hash, generate_approval_token
from shared.models import DispatchRequest


@pytest.mark.asyncio
async def test_mailer_dry_run():
    success, msg_id, err = await send_email(
        recipient="grievance@swiggy.in",
        subject="DPDPA Erasure Notice",
        body="Body of notice",
        request_id="req_test_01",
        mode="dry_run",
    )
    assert success is True
    assert msg_id is not None
    assert msg_id.startswith("<") and msg_id.endswith(">")
    assert err is None


@pytest.mark.asyncio
async def test_mailer_demo_redirect_rewrites_recipient():
    success, msg_id, err = await send_email(
        recipient="real_fiduciary@swiggy.in",
        subject="DPDPA Erasure Notice",
        body="Body text...",
        request_id="req_test_02",
        mode="demo_redirect",
        demo_override="demo-test-inbox@example.com",
    )
    assert success is True
    assert msg_id is not None
    assert err is None


@pytest.mark.asyncio
async def test_mailer_live_mode_refusal_when_unconfirmed():
    success, msg_id, err = await send_email(
        recipient="real_fiduciary@swiggy.in",
        subject="DPDPA Erasure Notice",
        body="Body text...",
        request_id="req_test_03",
        mode="live",
        confirm_live=False,  # Unconfirmed
    )
    assert success is False
    assert msg_id is None
    assert "CONFIRM_LIVE is false" in err


@pytest.mark.asyncio
async def test_dispatcher_rejects_unapproved_token():
    from agents.dispatcher.agent import handle_dispatch_request

    class MockContext:
        def __init__(self):
            self.sent_messages = []

        async def send(self, recipient, msg):
            self.sent_messages.append(msg)

    ctx = MockContext()
    invalid_req = DispatchRequest(
        session_id="sess_123",
        batch_id="batch_123",
        request_id="req_fail_1",
        company_name="Swiggy",
        recipient_email="grievance@swiggy.in",
        subject="Subject",
        body="Body",
        approval_token="invalid_forged_token_xyz",
        content_hash="hash_123",
        user_email="user@test.com",
    )

    await handle_dispatch_request(ctx, "agent_concierge", invalid_req)
    assert len(ctx.sent_messages) == 1
    res = ctx.sent_messages[0]
    assert res.status == "SEND_FAILED"
    assert "HMAC security verification failed" in res.error
