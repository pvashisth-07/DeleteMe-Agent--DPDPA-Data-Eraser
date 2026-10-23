import asyncio
from pathlib import Path
import sys
from typing import Optional

# Ensure project root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from uagents import Agent, Context, Model
from uagents.setup import fund_agent_if_low

from shared.clock import now_iso
from shared.config import get_settings
from shared.db import SqliteRepo
from shared.logging import setup_logger
from shared.models import InboundReply

logger = setup_logger("mock_company_agent")
settings = get_settings()
repo = SqliteRepo(settings.DB_PATH)

mock_company_agent = Agent(
    name="deleteme_mock_company",
    seed=settings.MOCK_COMPANY_SEED,
    port=8006,
    endpoint=["http://127.0.0.1:8006/submit"],
    mailbox=bool(settings.AGENT_MAILBOX_KEY),
    publish_agent_details=False,
)


class TriggerMockReply(Model):
    request_id: str
    company_name: str
    stage: Optional[str] = None  # "ack" | "resolved" | "partial"


SWIGGY_ACK_BODY = """Hello,

Thank you for contacting Swiggy Data Privacy Helpdesk.
Your request regarding account data rights has been successfully registered in our customer grievance tracking system.

Ticket Reference Number: SWIGGY-DPDP-8821
Estimated Processing Time: 30 days

Our Data Protection Officer will review your submission and communicate the outcome in accordance with the Digital Personal Data Protection Act, 2023.

Best Regards,
Swiggy Privacy Operations (SIMULATED)
Ticket ID: SWIGGY-DPDP-8821
"""

SWIGGY_RESOLVED_BODY = """Dear Data Principal,

We are writing to confirm that your request for erasure under the Digital Personal Data Protection Act has been successfully executed.

All personal data, profile identifiers, behavioral tracking records, saved delivery addresses, and user account history associated with your registered email have been permanently deleted and purged from all Swiggy active databases and data processor systems.

Confirmation Reference: SWIGGY-PURGE-CONFIRMED-9921
Status: Erasure Complete (SIMULATED)

Sincerely,
Swiggy Data Protection Office
"""

ZOMATO_PARTIAL_BODY = """Dear Customer,

In response to your personal data erasure request, we have deleted your Zomato user profile, saved payment instruments, personalized marketing preferences, and loyalty program history.

However, please be informed of a partial retention:
Pursuant to mandatory statutory obligations under Section 44AA of the Income Tax Act, 1961 and the Central Goods and Services Tax (CGST) Act, 2017, we are legally required to retain transaction invoices, financial payment receipts, and delivery tax ledgers for a statutory retention period of 7 years from the end of the relevant financial year.

Retained Items:
- GST Tax Invoices
- Past Order Financial Receipts
- Ledger Transaction Records

These records have been isolated, archived, and access is restricted solely to authorized compliance audits. (SIMULATED)

Regards,
Zomato Legal & Compliance Team
"""


async def send_simulated_reply(
    ctx: Context,
    tracker_address: str,
    request_id: str,
    company_name: str,
    subject: str,
    body: str,
    session_id: Optional[str] = None,
    batch_id: Optional[str] = None,
):
    reply_msg = InboundReply(
        session_id=session_id,
        batch_id=batch_id,
        request_id=request_id,
        company_name=company_name,
        from_email=f"grievance@{company_name.lower().replace(' ', '')}.com",
        subject=f"[SIMULATED] {subject}",
        body=body,
        received_at=now_iso(),
    )
    logger.info(f"[SIMULATED COMPANY] Sending reply for {company_name} to tracker: {subject}")
    await ctx.send(tracker_address, reply_msg)


@mock_company_agent.on_message(model=TriggerMockReply)
async def handle_trigger(ctx: Context, sender: str, msg: TriggerMockReply):
    tracker_addr = Agent(seed=settings.TRACKER_SEED).address
    comp = msg.company_name.lower()
    req = repo.get_request(msg.request_id)
    session_id = req.get("session_id") if req else None
    batch_id = req.get("batch_id") if req else None

    if "swiggy" in comp:
        if msg.stage == "resolved":
            await send_simulated_reply(
                ctx, tracker_addr, msg.request_id, "Swiggy",
                "Confirmation of Erasure [Ref: SWIGGY-DPDP-8821]", SWIGGY_RESOLVED_BODY,
                session_id=session_id, batch_id=batch_id,
            )
        else:
            await send_simulated_reply(
                ctx, tracker_addr, msg.request_id, "Swiggy",
                "Acknowledgment of Erasure Request [Ref: SWIGGY-DPDP-8821]", SWIGGY_ACK_BODY,
                session_id=session_id, batch_id=batch_id,
            )
    elif "zomato" in comp:
        await send_simulated_reply(
            ctx, tracker_addr, msg.request_id, "Zomato",
            "Resolution of Erasure Request [Ref: ZOMATO-DPDP-4412]", ZOMATO_PARTIAL_BODY,
            session_id=session_id, batch_id=batch_id,
        )
    elif "paytm" in comp:
        logger.info("[SIMULATED COMPANY] Paytm is intentionally unresponsive (testing OVERDUE and Escalation).")


# Memory tracker to avoid repeatedly re-sending in on_interval
_SENT_MOCK_ACTIONS = set()


@mock_company_agent.on_interval(period=3.0)
async def sweep_and_respond(ctx: Context):
    """
    Automated demo sweep: checks requests in DB and simulates company responses
    for the canonical scenario (Swiggy -> Ack then Resolved; Zomato -> Partial; Paytm -> silent).
    """
    tracker_addr = Agent(seed=settings.TRACKER_SEED).address
    open_reqs = repo.get_all_open_requests()

    for r in open_reqs:
        req_id = r["request_id"]
        comp = r.get("company_name", "").lower()
        state = r.get("state", "")
        session_id = r.get("session_id")
        batch_id = r.get("batch_id")

        if "swiggy" in comp:
            if state == "SENT" and f"{req_id}_ack" not in _SENT_MOCK_ACTIONS:
                _SENT_MOCK_ACTIONS.add(f"{req_id}_ack")
                await send_simulated_reply(
                    ctx, tracker_addr, req_id, "Swiggy",
                    "Acknowledgment of Erasure Request [Ref: SWIGGY-DPDP-8821]", SWIGGY_ACK_BODY,
                    session_id=session_id, batch_id=batch_id,
                )
            elif state == "ACKNOWLEDGED" and f"{req_id}_resolved" not in _SENT_MOCK_ACTIONS:
                _SENT_MOCK_ACTIONS.add(f"{req_id}_resolved")
                await send_simulated_reply(
                    ctx, tracker_addr, req_id, "Swiggy",
                    "Confirmation of Erasure [Ref: SWIGGY-DPDP-8821]", SWIGGY_RESOLVED_BODY,
                    session_id=session_id, batch_id=batch_id,
                )
        elif "zomato" in comp:
            if state == "SENT" and f"{req_id}_partial" not in _SENT_MOCK_ACTIONS:
                _SENT_MOCK_ACTIONS.add(f"{req_id}_partial")
                await send_simulated_reply(
                    ctx, tracker_addr, req_id, "Zomato",
                    "Resolution of Erasure Request [Ref: ZOMATO-DPDP-4412]", ZOMATO_PARTIAL_BODY,
                    session_id=session_id, batch_id=batch_id,
                )
        elif "paytm" in comp:
            # Paytm is unresponsive
            pass


@mock_company_agent.on_event("startup")
async def on_startup(ctx: Context):
    fund_agent_if_low(mock_company_agent.wallet.address())
    logger.info(f"Mock Company Agent (SIMULATED) online at: {mock_company_agent.address}")


if __name__ == "__main__":
    mock_company_agent.run()
