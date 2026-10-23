import os
import sys
from pathlib import Path
from uuid import uuid4

# Ensure project root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from uagents import Agent, Context
from uagents.setup import fund_agent_if_low
from uagents_core.contrib.protocols.chat import ChatMessage, TextContent

from agents.concierge.intent import extract_intent
from agents.concierge.session import (
    ConciergeSession,
    SessionState,
    load_session,
    save_session,
)
from agents.concierge.cards import (
    build_confirmation_card,
    build_reply_card,
    build_review_card,
    build_status_card,
)
from agents.concierge.orchestrator import orchestrate_batch_discovery_and_drafting
from mcp.tools import compute_content_hash
from shared.acp import build_chat_protocol, make_text_reply
from shared.approval import compute_drafts_content_hash, generate_approval_token
from shared.clock import now_iso
from shared.config import get_law_config, get_settings
from shared.db import SqliteRepo
from shared.logging import global_trace_collector, setup_logger

logger = setup_logger("concierge_agent")
settings = get_settings()
repo = SqliteRepo(settings.DB_PATH)

COMMAND_FOOTER = "\n\n---\n*Commands: YES to confirm | REMOVE <company> | CANCEL | STATUS | DEBUG*"

# Initialize Concierge Agent
is_mailbox = bool(settings.AGENT_MAILBOX_KEY or settings.AGENTVERSE_KEY or settings.AGENTVERSE_API_KEY)
concierge_agent = Agent(
    name="deleteme_concierge",
    seed=settings.CONCIERGE_SEED,
    port=8001,
    endpoint=None if is_mailbox else ["http://127.0.0.1:8001/submit"],
    mailbox=is_mailbox,
    publish_agent_details=True,
)


def get_disclaimer() -> str:
    law = get_law_config()
    return f"ℹ️ *Notice: {law.get('disclaimer', 'This is general information, not legal advice.')}*\n\n"


async def handle_chat_message(ctx: Context, sender: str, msg: ChatMessage) -> None:
    # Extract inbound text content
    text = ""
    for item in msg.content:
        if isinstance(item, TextContent):
            text += item.text + " "
        elif hasattr(item, "text"):
            text += getattr(item, "text") + " "
    text = text.strip()

    session_id = sender
    sess = load_session(repo, session_id)

    # Check session expiration
    if sess.state == SessionState.EXPIRED:
        reply_text = "This batch expired after 30 minutes. Nothing was sent. Say 'start again' or tell me which companies you want to be deleted from."
        sess.state = SessionState.NEW
        save_session(repo, sess)
        await ctx.send(sender, make_text_reply(reply_text))
        return

    # One-time disclaimer prefix
    prefix = ""
    if not sess.disclaimer_shown:
        prefix = get_disclaimer()
        sess.disclaimer_shown = True

    # Intent extraction
    extraction, err_msg = await extract_intent(text)
    if err_msg:
        await ctx.send(sender, make_text_reply(prefix + err_msg))
        return

    intent = extraction.intent
    logger.info(f"Concierge processing intent '{intent}' from {sender[:10]}...")

    # Route deterministic commands
    if intent == "status":
        reqs = repo.get_requests_for_session(sess.session_id)
        if not reqs:
            reqs = repo.get_all_open_requests()
        if not reqs:
            reqs = repo.get_recent_requests(limit=10)

        if not reqs:
            reply = f"{prefix}You have no active deletion requests.\nTo start, tell me which apps to delete you from (e.g., 'Delete me from Swiggy, Zomato and Paytm')."
            await ctx.send(sender, make_text_reply(reply))
        else:
            table = [
                "| Company | Status | Ticket ID | Deadline | Verified | Payment |",
                "|---|---|---|---|---|---|",
            ]
            pay_label = "💡 Demo Bypass" if settings.PAYMENTS_BYPASS_FOR_DEMO else "💳 Confirmed"
            for r in reqs:
                st = r.get("state", "UNKNOWN")
                dl = (r.get("deadline_at") or "N/A")[:10]
                tkt = r.get("ticket_id") or "Pending"
                v_badge = "✅ Yes" if r.get("verified", 1) else "⚠️ No"
                table.append(
                    f"| {r['company_name']} | `{st}` | {tkt} | {dl} | {v_badge} | {pay_label} |"
                )
            reply = f"{prefix}### DPDPA Erasure Requests Status\n\n" + "\n".join(table) + COMMAND_FOOTER
            card = build_status_card(reqs, payment_status=pay_label)
            await ctx.send(sender, make_text_reply(reply, metadata=card))
        return

    if intent == "debug":
        trace_str = global_trace_collector.format_debug_trace()
        reply = f"{prefix}```\n{trace_str}\n```" + COMMAND_FOOTER
        await ctx.send(sender, make_text_reply(reply))
        return

    if intent == "cancel":
        sess.state = SessionState.CANCELLED
        save_session(repo, sess)
        reply = f"{prefix}Your deletion request has been cancelled. No emails have been dispatched."
        await ctx.send(sender, make_text_reply(reply))
        return

    if intent == "approve":
        batch_id = extraction.raw_parameters.get("batch_id") or sess.batch_id
        if not batch_id:
            await ctx.send(sender, make_text_reply(f"{prefix}No active batch to approve. Please submit your companies first."))
            return

        drafts = repo.get_drafts_for_batch(batch_id)
        if not drafts:
            await ctx.send(sender, make_text_reply(f"{prefix}No drafted notices found for batch `{batch_id}`. Reply YES to draft first."))
            return

        content_hash = compute_drafts_content_hash(drafts)
        token = generate_approval_token(batch_id, session_id, content_hash)
        repo.save_batch(batch_id, session_id, content_hash, "APPROVED", approval_token=token)

        # Payment Protocol Gate: Process User -> Concierge Payment
        from shared.payments import process_user_batch_payment, process_inter_agent_micropayment
        from agents.concierge.registry import resolve_agent_address
        authorized, payment_ref, payment_label = await process_user_batch_payment(
            repo=repo,
            user_address=sender,
            concierge_address=concierge_agent.address,
            batch_id=batch_id,
        )
        if not authorized:
            await ctx.send(sender, make_text_reply(f"{prefix}Payment authorization failed for batch `{batch_id}`. Please retry."))
            return

        # Process Inter-Agent Micropayments (Concierge -> Discovery & Tracker)
        disc_addr = await resolve_agent_address("discovery")
        track_addr = await resolve_agent_address("tracker")
        for d in drafts:
            await process_inter_agent_micropayment(repo, concierge_agent.address, disc_addr, "discovery_lookup_fee", d["request_id"])
            await process_inter_agent_micropayment(repo, concierge_agent.address, track_addr, "tracking_fee", d["request_id"])

        # Dispatch all approved drafts in batch
        from agents.dispatcher.agent import handle_dispatch_request
        from shared.models import DispatchRequest

        dispatch_results = []
        for d in drafts:
            disp_req = DispatchRequest(
                session_id=session_id,
                batch_id=batch_id,
                request_id=d["request_id"],
                company_name=d["company_name"],
                recipient_email=d["recipient_email"],
                subject=d["subject"],
                body=d["body"],
                approval_token=token,
                content_hash=d["content_hash"],
                user_email=sess.user_email or "",
                payment_ref=payment_ref,
            )
            class DispCtx:
                def __init__(self):
                    self.result = None
                async def send(self, _, res):
                    self.result = res
            dctx = DispCtx()
            await handle_dispatch_request(dctx, concierge_agent.address, disp_req)
            if dctx.result:
                dispatch_results.append(dctx.result)
                if dctx.result.status == "SENT":
                    # Handoff to Tracker agent
                    from agents.tracker.agent import handle_track_request
                    from shared.models import TrackRequest
                    track_req = TrackRequest(
                        session_id=session_id,
                        batch_id=batch_id,
                        request_id=d["request_id"],
                        company_name=d["company_name"],
                        recipient_email=d["recipient_email"],
                        user_email=sess.user_email or "",
                        sent_at=dctx.result.sent_at or now_iso(),
                        deadline_at=dctx.result.deadline_at or now_iso(),
                        subject=d["subject"],
                        payment_ref=payment_ref,
                    )
                    class TrackCtx:
                        async def send(self, _, msg):
                            pass
                    await handle_track_request(TrackCtx(), concierge_agent.address, track_req)

        sess.state = SessionState.TRACKING
        save_session(repo, sess)

        lines = [
            f"{prefix}🚀 **Batch Approved & Dispatched!**\n",
            f"{payment_label}\n",
            f"- **Batch ID:** `{batch_id}`",
            f"- **HMAC Approval Token:** `{token[:16]}...`",
            f"- **Send Mode:** `{settings.SEND_MODE}`",
            "- **Statutory Response Window:** 30 Days\n",
            "### Dispatch Status:",
        ]
        for res in dispatch_results:
            icon = "✅" if res.status == "SENT" else "❌"
            deadline_str = res.deadline_at[:10] if res.deadline_at else "N/A"
            lines.append(f"{icon} **{res.company_name}**: `{res.status}` | Deadline: `{deadline_str}` (Ref: `{res.request_id}`)")

        lines.append("\nOur autonomous tracker is now monitoring for replies and 30-day statutory deadlines.")
        lines.append("Type `STATUS` at any time to inspect your active requests.")
        reply = "\n".join(lines)
        await ctx.send(sender, make_text_reply(reply))
        return

    if intent == "reply_paste":
        company = extraction.companies[0] if extraction.companies else ""
        open_reqs = repo.get_all_open_requests()
        matched_req = None
        if company:
            matched_req = next((r for r in open_reqs if r.get("company_name", "").lower() == company.lower()), None)
        if not matched_req and open_reqs:
            matched_req = open_reqs[0]

        if matched_req:
            from agents.tracker.agent import handle_inbound_reply
            from shared.models import InboundReply
            inbound_msg = InboundReply(
                session_id=sess.session_id,
                batch_id=matched_req.get("batch_id"),
                request_id=matched_req["request_id"],
                company_name=matched_req["company_name"],
                from_email=matched_req.get("recipient_email", ""),
                subject=f"Re: Data Erasure Request - {matched_req['company_name']}",
                body=text,
                received_at=now_iso(),
            )
            class InboundCtx:
                async def send(self, _, msg):
                    pass
            await handle_inbound_reply(InboundCtx(), concierge_agent.address, inbound_msg)

            updated = repo.get_request(matched_req["request_id"]) or {}
            st = updated.get("state", "PROCESSED")
            tkt = updated.get("ticket_id") or "N/A"
            card = build_reply_card(
                company=matched_req["company_name"],
                label=st,
                ticket_id=tkt,
                retained_items=[],
                explanation=f"Inbound reply classified as {st} for {matched_req['company_name']}.",
            )
            reply = (
                f"{prefix}📥 **Inbound Reply Processed for {matched_req['company_name']}**\n"
                f"- **Classified State:** `{st}`\n"
                f"- **Ticket Reference:** `{tkt}`\n\n"
                f"Type `STATUS` to inspect active tracking progress."
            )
            await ctx.send(sender, make_text_reply(reply + COMMAND_FOOTER, metadata=card))
            return
        else:
            await ctx.send(sender, make_text_reply(f"{prefix}No active requests found to associate this reply with."))
            return

    if intent == "edit":
        company = extraction.companies[0] if extraction.companies else ""
        instruction = extraction.raw_parameters.get("instruction", "")
        batch_id = sess.batch_id
        drafts = repo.get_drafts_for_batch(batch_id) if batch_id else []
        matched = next((d for d in drafts if d["company_name"].lower() == company.lower()), None)
        if matched:
            new_body = matched["body"] + f"\n\nAdditional Note: {instruction}"
            new_hash = compute_content_hash(matched["subject"], new_body, matched["recipient_email"])
            repo.save_draft(
                request_id=matched["request_id"],
                batch_id=batch_id,
                session_id=session_id,
                company_name=matched["company_name"],
                recipient_email=matched["recipient_email"],
                subject=matched["subject"],
                body=new_body,
                content_hash=new_hash,
                verified=bool(matched["verified"]),
            )
            # Invalidate previous approval token
            updated_drafts = repo.get_drafts_for_batch(batch_id)
            new_batch_hash = compute_drafts_content_hash(updated_drafts)
            repo.save_batch(batch_id, session_id, new_batch_hash, "AWAITING_APPROVAL", approval_token=None)
            sess.state = SessionState.AWAITING_APPROVAL
            save_session(repo, sess)

            card = build_review_card(batch_id, settings.SEND_MODE, updated_drafts)
            reply = (
                f"{prefix}📝 Updated draft for **{company}** with: *\"{instruction}\"*.\n"
                f"Previous approval token **invalidated** (new hash: `{new_batch_hash[:12]}...`).\n\n"
                f"**To approve updated batch, reply:** `APPROVE {batch_id}`"
            )
            await ctx.send(sender, make_text_reply(reply, metadata=card))
            return
        else:
            await ctx.send(sender, make_text_reply(f"{prefix}Company '{company}' not found in active batch drafts."))
            return

    if intent == "remove":
        removed = extraction.companies
        sess.companies = [c for c in sess.companies if c.lower() not in [r.lower() for r in removed]]
        batch_id = sess.batch_id
        if batch_id:
            existing_drafts = repo.get_drafts_for_batch(batch_id)
            remaining_drafts = [d for d in existing_drafts if d["company_name"].lower() not in [r.lower() for r in removed]]
            new_batch_hash = compute_drafts_content_hash(remaining_drafts) if remaining_drafts else ""
            repo.save_batch(batch_id, session_id, new_batch_hash, "AWAITING_APPROVAL", approval_token=None)
            sess.state = SessionState.AWAITING_APPROVAL
            save_session(repo, sess)

            card = build_review_card(batch_id, settings.SEND_MODE, remaining_drafts)
            reply = (
                f"{prefix}Removed **{', '.join(removed)}**.\n"
                f"Remaining companies: {', '.join([d['company_name'] for d in remaining_drafts]) or 'None'}.\n"
                f"Previous approval token **invalidated**.\n\n"
                f"**To approve updated batch, reply:** `APPROVE {batch_id}`"
            )
            await ctx.send(sender, make_text_reply(reply, metadata=card))
            return
        else:
            save_session(repo, sess)
            reply = f"{prefix}Removed {', '.join(removed)}. Remaining companies: {', '.join(sess.companies) if sess.companies else 'None'}."
            await ctx.send(sender, make_text_reply(reply + COMMAND_FOOTER))
            return

    if intent == "confirm" or text.lower() in ["yes", "confirm", "proceed"]:
        if sess.companies and sess.user_name and sess.user_email:
            drafts, failures, batch_hash = await orchestrate_batch_discovery_and_drafting(sess, repo)
            sections = []
            for d in drafts:
                badge = "✅ VERIFIED" if d["verified"] else "⚠️ UNVERIFIED (Please confirm)"
                preview = d["body"][:200].replace("\n", " ") + "..."
                sections.append(
                    f"### {d['company_name']} [{badge}]\n"
                    f"- **Recipient:** `{d['recipient_email']}`\n"
                    f"- **Subject:** {d['subject']}\n"
                    f"- **Preview:** *\"{preview}\"*\n"
                    f"- **Content SHA256:** `{d['content_hash'][:12]}...`"
                )

            fail_notes = ""
            if failures:
                fail_notes = "\n\n⚠️ **Partial Discovery Failures:**\n" + "\n".join([f"- {f['company']}: {f['reason']}" for f in failures])

            card = build_review_card(sess.batch_id, settings.SEND_MODE, drafts, failures)
            reply = (
                f"{prefix}## Review Your DPDPA Deletion Requests\n"
                f"**Batch ID:** `{sess.batch_id}` | **Send Mode:** `{settings.SEND_MODE}`\n\n"
                + "\n\n".join(sections)
                + fail_notes
                + f"\n\n**To dispatch these notices, reply:** `APPROVE {sess.batch_id}`\n"
                + "*Or customize: `EDIT <company>: <notes>` | `REMOVE <company>` | `CANCEL`*"
            )
            await ctx.send(sender, make_text_reply(reply, metadata=card))
        else:
            reply = f"{prefix}Please specify the companies and your account email before proceeding."
            await ctx.send(sender, make_text_reply(reply))
        return

    # Update session profile details if provided
    if extraction.name:
        sess.user_name = extraction.name
    if extraction.email:
        sess.user_email = extraction.email
    if extraction.phone:
        sess.user_phone = extraction.phone
    if extraction.identifiers:
        sess.data.setdefault("identifiers", {}).update(extraction.identifiers)

    # Update companies if found
    if extraction.companies:
        for c in extraction.companies:
            if c not in sess.companies:
                sess.companies.append(c)

    # Determine next conversation turn
    if not sess.companies:
        reply = (
            f"{prefix}Hello! I am DeleteMe, your autonomous DPDPA 2023 Rights Agent.\n\n"
            "Which apps or services would you like to delete your personal data from?\n"
            "(For example: *'Delete me from Swiggy, Zomato and Paytm'*)"
        )
        await ctx.send(sender, make_text_reply(reply))
        return

    # Check if identity is missing
    if not sess.user_name or not sess.user_email:
        sess.state = SessionState.NEED_IDENTITY
        save_session(repo, sess)
        missing = []
        if not sess.user_name:
            missing.append("your **full name**")
        if not sess.user_email:
            missing.append("your **registered email address**")

        reply = (
            f"{prefix}I found: **{', '.join(sess.companies)}**.\n\n"
            f"Under Section 12 of the DPDPA, companies require account verification to process erasure.\n"
            f"Please provide {' and '.join(missing)} so I can draft your legal requests."
        )
        await ctx.send(sender, make_text_reply(reply + COMMAND_FOOTER))
        return

    # Both companies and identity are available -> Confirmation step
    sess.state = SessionState.CONFIRM_COMPANIES
    save_session(repo, sess)
    reply = (
        f"{prefix}I found: **{', '.join(sess.companies)}**.\n\n"
        f"**Account Holder:** {sess.user_name}\n"
        f"**Registered Email:** {sess.user_email}\n"
        + (f"**Phone:** {sess.user_phone}\n" if sess.user_phone else "")
        + "\nReply **YES** to continue or edit the list with `REMOVE <company>`."
    )
    await ctx.send(sender, make_text_reply(reply + COMMAND_FOOTER))


# Include ACP protocol with manifest publishing enabled
chat_protocol = build_chat_protocol(handle_chat_message)
concierge_agent.include(chat_protocol, publish_manifest=True)


from shared.models import StatusUpdate


@concierge_agent.on_message(model=StatusUpdate)
async def handle_status_update(ctx: Context, sender: str, msg: StatusUpdate):
    logger.info(f"Concierge received StatusUpdate: {msg.company_name} -> {msg.state} (Details: {msg.details})")
    global_trace_collector.record_agent_call(
        agent_name="deleteme_tracker",
        agent_addr=sender,
        action=f"update:{msg.company_name}:{msg.state}",
        duration_ms=0,
        status=msg.state,
    )


@concierge_agent.on_event("startup")
async def on_startup(ctx: Context):
    fund_agent_if_low(concierge_agent.wallet.address())
    logger.info(f"Concierge Agent started with address: {concierge_agent.address}")
    global_trace_collector.record_agent_call(
        agent_name="deleteme_concierge",
        agent_addr=concierge_agent.address,
        action="startup",
        duration_ms=0,
        status="ONLINE",
    )


if __name__ == "__main__":
    concierge_agent.run()
