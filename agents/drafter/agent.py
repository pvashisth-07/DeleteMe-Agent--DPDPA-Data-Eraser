import sys
from pathlib import Path

# Ensure project root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from uagents import Agent, Context
from uagents.setup import fund_agent_if_low
from uagents_core.contrib.protocols.chat import ChatMessage, TextContent

from mcp.tools import draft_erasure_request_impl
from shared.acp import build_chat_protocol, make_text_reply
from shared.config import get_settings
from shared.logging import global_trace_collector, setup_logger
from shared.models import DraftRequest, DraftResult

logger = setup_logger("drafter_agent")
settings = get_settings()

drafter_agent = Agent(
    name="deleteme_drafter",
    seed=settings.DRAFTER_SEED,
    port=8004,
    endpoint=["http://127.0.0.1:8004/submit"],
    mailbox=bool(settings.AGENT_MAILBOX_KEY),
    publish_agent_details=True,
)


@drafter_agent.on_message(model=DraftRequest, replies=DraftResult)
async def handle_draft_request(ctx: Context, sender: str, msg: DraftRequest):
    logger.info(f"Drafter compiling DPDPA notice for {msg.company_name} (request_id: {msg.request_id})")

    global_trace_collector.record_mcp_call(tool="draft_erasure_request", duration_ms=8.0, status="OK")

    profile_dict = {
        "name": msg.user_profile.name,
        "email": msg.user_profile.email,
        "phone": msg.user_profile.phone,
        "identifiers": msg.user_profile.identifiers,
    }

    draft = draft_erasure_request_impl(
        company_name=msg.company_name,
        recipient_email=msg.recipient_email,
        user_profile=profile_dict,
        verified=msg.verified,
    )

    result = DraftResult(
        session_id=msg.session_id,
        batch_id=msg.batch_id,
        request_id=msg.request_id,
        company_name=draft["company_name"],
        recipient_email=draft["recipient_email"],
        subject=draft["subject"],
        body=draft["body"],
        content_hash=draft["content_hash"],
        verified=draft["verified"],
    )

    await ctx.send(sender, result)


async def handle_drafter_chat(ctx: Context, sender: str, msg: ChatMessage):
    """ACP handler allowing Drafter agent to be used standalone in chat."""
    text = ""
    for item in msg.content:
        if isinstance(item, TextContent) or hasattr(item, "text"):
            text += getattr(item, "text", "") + " "
    clean_text = text.strip()

    company = clean_text.replace("draft", "").replace("a", "").replace("dpdpa", "").replace("erasure request for", "").replace("for", "").strip()
    if not company:
        company = "Zomato"

    mock_profile = {
        "name": "Data Principal",
        "email": "user@example.com",
        "identifiers": {"user_id": "usr_sample"},
    }

    draft = draft_erasure_request_impl(
        company_name=company.title(),
        recipient_email=f"grievance@{company.lower()}.com",
        user_profile=mock_profile,
        verified=True,
    )

    reply = (
        f"### Draft DPDPA Section 12 Notice for {draft['company_name']}\n"
        f"**Subject:** {draft['subject']}\n"
        f"**Recipient:** `{draft['recipient_email']}`\n\n"
        f"```\n{draft['body']}\n```\n\n"
        f"**Content SHA256:** `{draft['content_hash'][:16]}...`"
    )
    await ctx.send(sender, make_text_reply(reply))


chat_proto = build_chat_protocol(handle_drafter_chat)
drafter_agent.include(chat_proto, publish_manifest=True)


@drafter_agent.on_event("startup")
async def on_startup(ctx: Context):
    fund_agent_if_low(drafter_agent.wallet.address())
    logger.info(f"Drafter Agent online at: {drafter_agent.address}")
    global_trace_collector.record_agent_call(
        agent_name="deleteme_drafter",
        agent_addr=drafter_agent.address,
        action="startup",
        duration_ms=0,
        status="ONLINE",
    )


if __name__ == "__main__":
    drafter_agent.run()
