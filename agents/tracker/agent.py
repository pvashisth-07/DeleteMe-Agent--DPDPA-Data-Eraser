from datetime import datetime, timedelta
from pathlib import Path
import sys
from typing import Dict, List, Optional

# Ensure project root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from uagents import Agent, Context
from uagents.setup import fund_agent_if_low
from uagents_core.contrib.protocols.chat import ChatMessage, TextContent

from agents.tracker.classifier import classify_reply
from agents.tracker.escalation import generate_escalation_draft, generate_followup_draft
from agents.tracker.state_machine import (
    TERMINAL_STATES,
    TrackerState,
    can_transition,
    is_deadline_active,
    transition_request,
)
from shared.acp import build_chat_protocol, make_text_reply
from shared.clock import now, now_iso
from shared.config import get_law_config, get_settings
from shared.db import SqliteRepo
from shared.logging import global_trace_collector, setup_logger
from shared.models import InboundReply, StatusUpdate, TrackRequest
from shared.payments import is_payment_authorized

logger = setup_logger("tracker_agent")
settings = get_settings()
repo = SqliteRepo(settings.DB_PATH)

tracker_agent = Agent(
    name="deleteme_tracker",
    seed=settings.TRACKER_SEED,
    port=8004,
    endpoint=["http://127.0.0.1:8004/submit"],
    mailbox=bool(settings.AGENT_MAILBOX_KEY),
    publish_agent_details=True,
)

# In-memory registry of open requests for fast polling
_OPEN_REQUESTS_CACHE: Dict[str, dict] = {}


def rehydrate_requests():
    """Rehydrates open active requests from database."""
    global _OPEN_REQUESTS_CACHE
    open_reqs = repo.get_all_open_requests()
    _OPEN_REQUESTS_CACHE = {r["request_id"]: r for r in open_reqs if r.get("state") not in TERMINAL_STATES}
    logger.info(f"Tracker rehydrated {len(_OPEN_REQUESTS_CACHE)} open request(s) from database.")


async def notify_concierge_status_update(
    ctx: Context,
    session_id: str,
    batch_id: str,
    request_id: str,
    company_name: str,
    state: str,
    ticket_id: Optional[str] = None,
    details: Optional[str] = None,
):
    """Sends proactive StatusUpdate to the Concierge agent."""
    concierge_addr = Agent(seed=settings.CONCIERGE_SEED).address
    update = StatusUpdate(
        session_id=session_id,
        batch_id=batch_id,
        request_id=request_id,
        company_name=company_name,
        state=state,
        ticket_id=ticket_id,
        details=details,
        updated_at=now_iso(),
    )
    logger.info(f"Sending StatusUpdate to Concierge: {company_name} -> {state} (Ticket: {ticket_id})")
    await ctx.send(concierge_addr, update)


@tracker_agent.on_message(model=TrackRequest)
async def handle_track_request(ctx: Context, sender: str, msg: TrackRequest):
    logger.info(f"Tracker received TrackRequest: {msg.company_name} [{msg.request_id}]")

    # Defense in depth: Check payment authorization
    if not is_payment_authorized(msg.payment_ref, bypass_for_demo=settings.PAYMENTS_BYPASS_FOR_DEMO):
        logger.error(f"Tracker rejected request {msg.request_id}: payment not authorized.")
        return

    # Record tracking request in memory
    req_dict = {
        "request_id": msg.request_id,
        "batch_id": msg.batch_id,
        "session_id": msg.session_id,
        "company_name": msg.company_name,
        "recipient_email": msg.recipient_email,
        "user_email": msg.user_email,
        "subject": msg.subject,
        "state": "SENT",
        "sent_at": msg.sent_at,
        "deadline_at": msg.deadline_at,
    }
    _OPEN_REQUESTS_CACHE[msg.request_id] = req_dict

    global_trace_collector.record_agent_call(
        agent_name="deleteme_tracker",
        agent_addr=tracker_agent.address,
        action=f"track:{msg.company_name}",
        duration_ms=5.0,
        status="TRACKING",
    )


@tracker_agent.on_message(model=InboundReply)
async def handle_inbound_reply(ctx: Context, sender: str, msg: InboundReply):
    logger.info(f"Tracker processing InboundReply from {msg.from_email} for {msg.company_name} [{msg.request_id}]")

    # Classify reply using ASI1 or rule-based fallback
    classification = await classify_reply(
        body=msg.body,
        subject=msg.subject,
        company_name=msg.company_name,
    )
    logger.info(f"Classified reply for {msg.company_name}: {classification.label} (Ticket: {classification.ticket_id})")

    if classification.label == "IRRELEVANT":
        logger.info(f"Ignored IRRELEVANT reply for {msg.company_name}")
        return

    req = repo.get_request(msg.request_id)
    if not req:
        logger.warning(f"Request {msg.request_id} not found in database for inbound reply.")
        return

    current_state = req.get("state", "SENT")
    target_state = classification.label  # ACKNOWLEDGED, RESOLVED, PARTIAL, REFUSED, NEEDS_INFO

    # Prepare event payload
    payload = {
        "ticket_id": classification.ticket_id,
        "retained_items": classification.retained_items,
        "legal_basis": classification.legal_basis,
        "retention_period": classification.retention_period,
        "needs_info_detail": classification.needs_info_detail,
        "plain_explanation": classification.plain_explanation,
    }

    success, reason = transition_request(
        repo=repo,
        request_id=msg.request_id,
        new_state=target_state,
        reason=classification.plain_explanation or f"Inbound {target_state} reply received",
        ticket_id=classification.ticket_id,
        payload=payload,
    )

    if success:
        if target_state in TERMINAL_STATES:
            _OPEN_REQUESTS_CACHE.pop(msg.request_id, None)
        else:
            updated_req = repo.get_request(msg.request_id)
            if updated_req:
                _OPEN_REQUESTS_CACHE[msg.request_id] = updated_req

        # Proactive StatusUpdate to Concierge
        await notify_concierge_status_update(
            ctx=ctx,
            session_id=req.get("session_id", ""),
            batch_id=req.get("batch_id", ""),
            request_id=msg.request_id,
            company_name=msg.company_name,
            state=target_state,
            ticket_id=classification.ticket_id,
            details=classification.plain_explanation,
        )


@tracker_agent.on_interval(period=1.5)
async def sweep_deadlines(ctx: Context):
    """
    Periodic statutory deadline sweep.
    Evaluates open requests against simulated demo clock.
    SENT / ACKNOWLEDGED / NEEDS_INFO -> OVERDUE -> follow-up
    FOLLOWUP_SENT -> ESCALATION_DRAFTED
    """
    sim_now = now()
    law_cfg = get_law_config()
    deadline_days = law_cfg.get("RESPONSE_DEADLINE_DAYS", 30)

    # Copy keys to avoid concurrent modification issues
    req_ids = list(_OPEN_REQUESTS_CACHE.keys())
    for req_id in req_ids:
        req = _OPEN_REQUESTS_CACHE.get(req_id)
        if not req:
            continue

        state = req.get("state", "SENT")
        if not is_deadline_active(state):
            continue

        deadline_str = req.get("deadline_at")
        if not deadline_str:
            continue

        try:
            deadline_dt = datetime.fromisoformat(deadline_str)
        except Exception:
            continue

        # Check if statutory deadline has elapsed
        if sim_now >= deadline_dt:
            company_name = req.get("company_name", "Company")
            session_id = req.get("session_id", "")
            batch_id = req.get("batch_id", "")
            ticket_id = req.get("ticket_id")

            if state in {TrackerState.SENT.value, TrackerState.ACKNOWLEDGED.value, TrackerState.NEEDS_INFO.value}:
                logger.warning(f"Statutory 30-day deadline elapsed for {company_name} [{req_id}]. Transitioning to OVERDUE.")
                
                # Transition to OVERDUE
                transition_request(
                    repo=repo,
                    request_id=req_id,
                    new_state=TrackerState.OVERDUE.value,
                    reason="Statutory response deadline elapsed without resolution.",
                    ticket_id=ticket_id,
                )

                # Generate follow-up notice
                sess = repo.get_session(session_id) or {}
                user_name = sess.get("user_name", "Data Principal")
                followup_draft = generate_followup_draft(
                    company_name=company_name,
                    user_name=user_name,
                    ticket_id=ticket_id,
                    original_date=req.get("sent_at", "")[:10],
                )

                # Set new deadline for follow-up
                new_deadline = (sim_now + timedelta(days=deadline_days)).isoformat()
                req["state"] = TrackerState.FOLLOWUP_SENT.value
                req["deadline_at"] = new_deadline
                _OPEN_REQUESTS_CACHE[req_id] = req

                # Transition to FOLLOWUP_SENT
                transition_request(
                    repo=repo,
                    request_id=req_id,
                    new_state=TrackerState.FOLLOWUP_SENT.value,
                    reason="Statutory follow-up notice drafted and dispatched.",
                    ticket_id=ticket_id,
                    payload={"subject": followup_draft.subject, "body": followup_draft.body},
                )

                await notify_concierge_status_update(
                    ctx=ctx,
                    session_id=session_id,
                    batch_id=batch_id,
                    request_id=req_id,
                    company_name=company_name,
                    state="FOLLOWUP_SENT",
                    ticket_id=ticket_id,
                    details=f"Statutory 30-day deadline expired. Follow-up notice sent for {company_name}.",
                )

            elif state == TrackerState.FOLLOWUP_SENT.value:
                logger.warning(f"Second deadline elapsed for {company_name} [{req_id}]. Grievance redressal exhausted.")

                sess = repo.get_session(session_id) or {}
                user_name = sess.get("user_name", "Data Principal")
                user_email = req.get("user_email") or sess.get("user_email", "")
                events = repo.get_events_for_request(req_id)

                escalation = generate_escalation_draft(
                    company_name=company_name,
                    user_name=user_name,
                    user_email=user_email,
                    fiduciary_contact=req.get("recipient_email", ""),
                    sent_at=req.get("sent_at", ""),
                    followup_at=deadline_str,
                    days_elapsed=60,
                    ticket_id=ticket_id,
                    correspondence_events=events,
                )

                # Transition to ESCALATION_DRAFTED
                transition_request(
                    repo=repo,
                    request_id=req_id,
                    new_state=TrackerState.ESCALATION_DRAFTED.value,
                    reason="Grievance redressal exhausted under Section 13(3). Escalation complaint prepared.",
                    ticket_id=ticket_id,
                    payload={"escalation": escalation.model_dump()},
                )

                _OPEN_REQUESTS_CACHE.pop(req_id, None)

                await notify_concierge_status_update(
                    ctx=ctx,
                    session_id=session_id,
                    batch_id=batch_id,
                    request_id=req_id,
                    company_name=company_name,
                    state="ESCALATION_DRAFTED",
                    ticket_id=ticket_id,
                    details=f"Grievance redressal exhausted for {company_name}. Formal Escalation Complaint drafted for Data Protection Board.",
                )


# ==============================================================================
# ACP Protocol Handler (ASI:One Chat Capability)
# ==============================================================================

async def handle_tracker_chat_message(ctx: Context, sender: str, msg: ChatMessage):
    """Answers ACP queries such as 'status of my requests' or 'status'."""
    text_content = ""
    for item in msg.content:
        if isinstance(item, TextContent):
            text_content += item.text + " "

    open_reqs = repo.get_all_open_requests()
    lines = [
        "📊 **DeleteMe Autonomous Tracker Status**\n",
        f"- **Simulated Clock:** `{now().strftime('%Y-%m-%d %H:%M:%S UTC')}`",
        f"- **Speed Multiplier:** `{settings.DEMO_CLOCK_SPEED}x`",
        f"- **Active Monitored Requests:** {len(open_reqs)}\n",
    ]

    if not open_reqs:
        lines.append("No active requests currently monitored.")
    else:
        for r in open_reqs:
            state = r.get("state", "UNKNOWN")
            comp = r.get("company_name", "Unknown")
            dl = (r.get("deadline_at") or "")[:10]
            tkt = r.get("ticket_id") or "Pending"
            lines.append(f"- **{comp}**: `{state}` | Ticket: `{tkt}` | Deadline: `{dl}`")

    lines.append("\n*DPDPA 2023 Compliance Engine | fetch.ai uAgents*")
    await ctx.send(sender, make_text_reply("\n".join(lines)))


chat_proto = build_chat_protocol(handler=handle_tracker_chat_message)
tracker_agent.include(chat_proto, publish_manifest=True)


@tracker_agent.on_event("startup")
async def on_startup(ctx: Context):
    fund_agent_if_low(tracker_agent.wallet.address())
    rehydrate_requests()
    logger.info(f"Tracker Agent online at: {tracker_agent.address}")


if __name__ == "__main__":
    tracker_agent.run()
