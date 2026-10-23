from datetime import timedelta
from pathlib import Path
import sys

# Ensure project root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from uagents import Agent, Context
from uagents.setup import fund_agent_if_low

from agents.dispatcher.mailer import send_email
from shared.approval import verify_approval_token
from shared.clock import now, now_iso
from shared.config import get_law_config, get_settings
from shared.db import SqliteRepo
from shared.logging import global_trace_collector, setup_logger
from shared.models import DispatchRequest, DispatchResult
from shared.payments import is_payment_authorized

logger = setup_logger("dispatcher_agent")
settings = get_settings()
repo = SqliteRepo(settings.DB_PATH)

dispatcher_agent = Agent(
    name="deleteme_dispatcher",
    seed=settings.DISPATCHER_SEED,
    port=8005,
    endpoint=["http://127.0.0.1:8005/submit"],
    mailbox=bool(settings.AGENT_MAILBOX_KEY),
    publish_agent_details=False,  # Internal only: no public ACP
)


@dispatcher_agent.on_message(model=DispatchRequest, replies=DispatchResult)
async def handle_dispatch_request(ctx: Context, sender: str, msg: DispatchRequest):
    logger.info(f"Dispatcher processing request {msg.request_id} for {msg.company_name} (batch: {msg.batch_id})")

    # Defense in Depth Step 1: Re-verify Payment Status (Bypassed if PAYMENTS_BYPASS_FOR_DEMO is true)
    if not is_payment_authorized(msg.payment_ref, bypass_for_demo=settings.PAYMENTS_BYPASS_FOR_DEMO):
        logger.error(f"Dispatch rejected for {msg.request_id}: payment not authorized")
        await ctx.send(
            sender,
            DispatchResult(
                session_id=msg.session_id,
                batch_id=msg.batch_id,
                request_id=msg.request_id,
                company_name=msg.company_name,
                status="SEND_FAILED",
                error="Payment authorization missing or unconfirmed.",
            ),
        )
        return

    # Defense in Depth Step 2: Re-verify HMAC Approval Token and Content Hash
    single_draft = [{
        "company_name": msg.company_name,
        "recipient_email": msg.recipient_email,
        "subject": msg.subject,
        "body": msg.body,
        "content_hash": msg.content_hash,
    }]
    # Also fetch all drafts for batch if stored
    batch_drafts = repo.get_drafts_for_batch(msg.batch_id)
    eval_drafts = batch_drafts if batch_drafts else single_draft

    is_token_valid, reason = verify_approval_token(
        token=msg.approval_token,
        batch_id=msg.batch_id,
        session_id=msg.session_id,
        drafts=eval_drafts,
    )
    if not is_token_valid:
        logger.error(f"Dispatch security violation for {msg.request_id}: {reason}")
        await ctx.send(
            sender,
            DispatchResult(
                session_id=msg.session_id,
                batch_id=msg.batch_id,
                request_id=msg.request_id,
                company_name=msg.company_name,
                status="SEND_FAILED",
                error=f"HMAC security verification failed: {reason}",
            ),
        )
        return

    # Step 3: Dispatch email via configured send mode
    success, msg_id, err = await send_email(
        recipient=msg.recipient_email,
        subject=msg.subject,
        body=msg.body,
        request_id=msg.request_id,
        user_email=msg.user_email,
    )

    sent_time = now()
    sent_at_iso = sent_time.isoformat()
    law_cfg = get_law_config()
    deadline_days = law_cfg.get("RESPONSE_DEADLINE_DAYS", 30)
    deadline_iso = (sent_time + timedelta(days=deadline_days)).isoformat()

    if success:
        # Save request to database in SENT state
        repo.save_request(
            request_id=msg.request_id,
            batch_id=msg.batch_id,
            session_id=msg.session_id,
            company_name=msg.company_name,
            recipient_email=msg.recipient_email,
            user_email=msg.user_email,
            subject=msg.subject,
            body=msg.body,
            state="SENT",
            sent_at=sent_at_iso,
            deadline_at=deadline_iso,
        )
        repo.record_event(
            request_id=msg.request_id,
            batch_id=msg.batch_id,
            session_id=msg.session_id,
            from_state="APPROVED",
            to_state="SENT",
            reason=f"Dispatched via mode: {settings.SEND_MODE}",
            payload={"message_id": msg_id},
        )
        global_trace_collector.record_agent_call(
            agent_name="deleteme_dispatcher",
            agent_addr=dispatcher_agent.address,
            action=f"dispatch:{msg.company_name}",
            duration_ms=15.0,
            status="SENT",
        )
        await ctx.send(
            sender,
            DispatchResult(
                session_id=msg.session_id,
                batch_id=msg.batch_id,
                request_id=msg.request_id,
                company_name=msg.company_name,
                status="SENT",
                message_id=msg_id,
                sent_at=sent_at_iso,
                deadline_at=deadline_iso,
            ),
        )
    else:
        logger.error(f"Dispatch failed for {msg.company_name}: {err}")
        repo.update_request_state(msg.request_id, "SEND_FAILED", reason=err)
        await ctx.send(
            sender,
            DispatchResult(
                session_id=msg.session_id,
                batch_id=msg.batch_id,
                request_id=msg.request_id,
                company_name=msg.company_name,
                status="SEND_FAILED",
                error=err,
            ),
        )


@dispatcher_agent.on_event("startup")
async def on_startup(ctx: Context):
    fund_agent_if_low(dispatcher_agent.wallet.address())
    logger.info(f"Dispatcher Agent online at: {dispatcher_agent.address} (Mode: {settings.SEND_MODE})")
    global_trace_collector.record_agent_call(
        agent_name="deleteme_dispatcher",
        agent_addr=dispatcher_agent.address,
        action="startup",
        duration_ms=0,
        status="ONLINE",
    )


if __name__ == "__main__":
    dispatcher_agent.run()
