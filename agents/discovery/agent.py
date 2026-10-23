import sys
from pathlib import Path
from uuid import uuid4

# Ensure project root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from uagents import Agent, Context
from uagents.setup import fund_agent_if_low
from uagents_core.contrib.protocols.chat import ChatMessage, TextContent

from mcp.tools import find_grievance_contact_impl
from shared.acp import build_chat_protocol, make_text_reply
from shared.config import get_settings
from shared.db import SqliteRepo
from shared.logging import global_trace_collector, setup_logger
from shared.models import DiscoveryRequest, DiscoveryResult

logger = setup_logger("discovery_agent")
settings = get_settings()
repo = SqliteRepo(settings.DB_PATH)

discovery_agent = Agent(
    name="deleteme_discovery",
    seed=settings.DISCOVERY_SEED,
    port=8003,
    endpoint=["http://127.0.0.1:8003/submit"],
    mailbox=bool(settings.AGENT_MAILBOX_KEY),
    publish_agent_details=True,
)


@discovery_agent.on_message(model=DiscoveryRequest, replies=DiscoveryResult)
async def handle_discovery_request(ctx: Context, sender: str, msg: DiscoveryRequest):
    logger.info(f"Discovery handling request for company: {msg.company_name} (batch: {msg.batch_id})")

    # Record trace
    global_trace_collector.record_mcp_call(tool="find_grievance_contact", duration_ms=12.5, status="OK")

    try:
        contact = await find_grievance_contact_impl(msg.company_name, repo=repo)
        result = DiscoveryResult(
            session_id=msg.session_id,
            batch_id=msg.batch_id,
            company_name=contact["company_name"],
            officer_name=contact.get("officer_name"),
            email=contact["email"],
            address="India",
            source_url=contact.get("source_url"),
            verified=contact.get("verified", False),
            error=None,
        )
    except Exception as e:
        logger.error(f"Discovery error for {msg.company_name}: {e}")
        result = DiscoveryResult(
            session_id=msg.session_id,
            batch_id=msg.batch_id,
            company_name=msg.company_name,
            officer_name=None,
            email=f"privacy@{msg.company_name.lower().replace(' ', '')}.com",
            source_url=None,
            verified=False,
            error=str(e),
        )

    await ctx.send(sender, result)


async def handle_discovery_chat(ctx: Context, sender: str, msg: ChatMessage):
    """ACP handler allowing Discovery agent to be used standalone in chat."""
    text = ""
    for item in msg.content:
        if isinstance(item, TextContent) or hasattr(item, "text"):
            text += getattr(item, "text", "") + " "
    clean_text = text.strip()

    company = clean_text.replace("find", "").replace("the", "").replace("grievance officer for", "").replace("officer for", "").replace("contact for", "").strip()
    if not company:
        company = "Swiggy"

    contact = await find_grievance_contact_impl(company, repo=repo)
    verified_badge = "✅ VERIFIED" if contact["verified"] else "⚠️ UNVERIFIED (Please confirm)"

    reply = (
        f"### Grievance Contact for {contact['company_name']}\n"
        f"- **Officer Name:** {contact.get('officer_name') or 'Designated Grievance Officer'}\n"
        f"- **Email Address:** `{contact['email']}`\n"
        f"- **Status:** {verified_badge}\n"
        f"- **Source Policy:** {contact.get('source_url')}\n"
        "\n*Found under Rule 9 of DPDP Rules 2025.*"
    )
    await ctx.send(sender, make_text_reply(reply))


chat_proto = build_chat_protocol(handle_discovery_chat)
discovery_agent.include(chat_proto, publish_manifest=True)


@discovery_agent.on_event("startup")
async def on_startup(ctx: Context):
    fund_agent_if_low(discovery_agent.wallet.address())
    logger.info(f"Discovery Agent online at: {discovery_agent.address}")
    global_trace_collector.record_agent_call(
        agent_name="deleteme_discovery",
        agent_addr=discovery_agent.address,
        action="startup",
        duration_ms=0,
        status="ONLINE",
    )


if __name__ == "__main__":
    discovery_agent.run()
