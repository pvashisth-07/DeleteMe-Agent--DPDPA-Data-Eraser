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
from shared.acp import build_chat_protocol, make_text_reply
from shared.clock import now_iso
from shared.config import get_law_config, get_settings
from shared.db import SqliteRepo
from shared.logging import global_trace_collector, setup_logger

logger = setup_logger("concierge_agent")
settings = get_settings()
repo = SqliteRepo(settings.DB_PATH)

COMMAND_FOOTER = "\n\n---\n*Commands: YES to confirm | REMOVE <company> | CANCEL | STATUS | DEBUG*"

# Initialize Concierge Agent
concierge_agent = Agent(
    name="deleteme_concierge",
    seed=settings.CONCIERGE_SEED,
    port=8001,
    endpoint=["http://127.0.0.1:8001/submit"],
    mailbox=bool(settings.AGENT_MAILBOX_KEY),
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
        reqs = repo.get_all_open_requests()
        if not reqs:
            reply = f"{prefix}You have no active deletion requests.\nTo start, tell me which apps to delete you from (e.g., 'Delete me from Swiggy, Zomato and Paytm')."
        else:
            table = ["| Company | State | Ticket ID | Deadline |", "|---|---|---|---|"]
            for r in reqs:
                table.append(
                    f"| {r['company_name']} | `{r['state']}` | {r.get('ticket_id') or 'Pending'} | {r.get('deadline_at', 'N/A')[:10]} |"
                )
            reply = f"{prefix}### Active Erasure Requests Status\n\n" + "\n".join(table) + COMMAND_FOOTER
        await ctx.send(sender, make_text_reply(reply))
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

    if intent == "remove":
        removed = extraction.companies
        sess.companies = [c for c in sess.companies if c.lower() not in [r.lower() for r in removed]]
        save_session(repo, sess)
        reply = f"{prefix}Removed {', '.join(removed)}. Remaining companies: {', '.join(sess.companies) if sess.companies else 'None'}."
        await ctx.send(sender, make_text_reply(reply + COMMAND_FOOTER))
        return

    if intent == "confirm" or text.lower() in ["yes", "confirm", "proceed"]:
        if sess.companies and sess.user_name and sess.user_email:
            sess.state = SessionState.DISCOVERING
            if not sess.batch_id:
                sess.batch_id = f"batch_{uuid4().hex[:8]}"
            save_session(repo, sess)
            reply = (
                f"{prefix}✅ Confirmed! Starting discovery and drafting for {', '.join(sess.companies)}.\n"
                f"Batch ID: `{sess.batch_id}`.\n"
                "Looking up grievance officers and drafting your Section 12 notices now..."
            )
        else:
            reply = f"{prefix}Please specify the companies and your account email before proceeding."
        await ctx.send(sender, make_text_reply(reply + COMMAND_FOOTER))
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
