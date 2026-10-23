import asyncio
import os
import re
import sys
import time
from pathlib import Path
from uuid import uuid4

# Ensure project root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# Set demo environment variables
os.environ["SEND_MODE"] = "demo_redirect"
os.environ["DEMO_CLOCK_SPEED"] = "86400"
os.environ["PAYMENTS_BYPASS_FOR_DEMO"] = "true"
os.environ["DEBUG_MODE"] = "true"

from uagents import Agent
from uagents_core.contrib.protocols.chat import (
    ChatAcknowledgement,
    ChatMessage,
    StartSessionContent,
    TextContent,
)

from agents.concierge.agent import concierge_agent, handle_chat_message
from agents.mock_company.agent import SWIGGY_ACK_BODY, SWIGGY_RESOLVED_BODY, ZOMATO_PARTIAL_BODY
from agents.tracker.agent import handle_inbound_reply, sweep_deadlines, tracker_agent
from shared.acp import send_ack
from shared.clock import get_clock, now, now_iso
from shared.config import get_settings
from shared.db import SqliteRepo
from shared.logging import global_trace_collector
from shared.models import InboundReply


async def run_full_demo():
    clock = get_clock()
    clock.reset(speed=86400.0)
    settings = get_settings()
    repo = SqliteRepo(settings.DB_PATH)

    print("=" * 80)
    print("   DELETEME AGENT: AUTONOMOUS DPDPA 2023 RIGHTS AGENT (DEMO RUN)")
    print("   Fetch-a-thon 3.0 | Fetch.ai uAgents + ASI:One | Indian Privacy Rights")
    print("=" * 80)
    print(f"[*] Simulated Clock Initialized: {now().strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print(f"[*] Demo Clock Speed: {clock.get_speed()}x (1 real sec = 1 simulated day)")
    print(f"[*] Send Mode: {settings.SEND_MODE} (All emails redirected to demo inbox)")
    print(f"[*] Concierge Agent Address: {concierge_agent.address}")
    print(f"[*] Tracker Agent Address:   {tracker_agent.address}\n")

    class MockUserContext:
        def __init__(self):
            self.replies = []
            self.acks = []

        async def send(self, recipient: str, msg):
            if isinstance(msg, ChatAcknowledgement):
                self.acks.append(msg)
                print(f"   [ACP ACK] Acknowledged message ID: {str(msg.acknowledged_msg_id)[:8]}...")
            elif isinstance(msg, ChatMessage):
                self.replies.append(msg)
                for item in msg.content:
                    if hasattr(item, "text"):
                        print("\n" + "-" * 40 + " [AGENT CHAT REPLY] " + "-" * 40)
                        print(item.text)
                        print("-" * 100 + "\n")

    user_ctx = MockUserContext()
    user_addr = f"agent1q_consumer_user_{uuid4().hex[:8]}"

    # Turn 1: Inbound consumer request
    print(">>> [USER CHAT]: 'Delete me from Swiggy, Zomato and Paytm'")
    turn1_msg = ChatMessage(
        timestamp=int(now().timestamp()),
        msg_id=uuid4(),
        content=[StartSessionContent(), TextContent(type="text", text="Delete me from Swiggy, Zomato and Paytm")],
    )
    await send_ack(user_ctx, user_addr, turn1_msg)
    await handle_chat_message(user_ctx, user_addr, turn1_msg)

    # Turn 2: User provides identity
    print(">>> [USER CHAT]: 'My name is Aarav Sharma, email is aarav@example.com'")
    turn2_msg = ChatMessage(
        timestamp=int(now().timestamp()),
        msg_id=uuid4(),
        content=[TextContent(type="text", text="My name is Aarav Sharma, email is aarav@example.com")],
    )
    await send_ack(user_ctx, user_addr, turn2_msg)
    await handle_chat_message(user_ctx, user_addr, turn2_msg)

    # Turn 3: User confirms review
    print(">>> [USER CHAT]: 'YES'")
    turn3_msg = ChatMessage(
        timestamp=int(now().timestamp()),
        msg_id=uuid4(),
        content=[TextContent(type="text", text="YES")],
    )
    await send_ack(user_ctx, user_addr, turn3_msg)
    await handle_chat_message(user_ctx, user_addr, turn3_msg)

    last_reply = user_ctx.replies[-1].content[0].text
    batch_match = re.search(r"batch_[a-zA-Z0-9]+", last_reply)
    batch_id = batch_match.group(0) if batch_match else "batch_demo_001"

    # Turn 4: User Approves Batch
    print(f">>> [USER CHAT]: 'APPROVE {batch_id}'")
    turn4_msg = ChatMessage(
        timestamp=int(now().timestamp()),
        msg_id=uuid4(),
        content=[TextContent(type="text", text=f"APPROVE {batch_id}")],
    )
    await send_ack(user_ctx, user_addr, turn4_msg)
    await handle_chat_message(user_ctx, user_addr, turn4_msg)

    # Retrieve created requests from DB
    reqs = repo.get_all_open_requests()
    print(f"\n[+] Requests Dispatched and Monitored: {len(reqs)}")
    for r in reqs:
        print(f"    - {r['company_name']}: ID `{r['request_id']}` | Deadline: `{r.get('deadline_at', '')[:10]}`")

    # Step 5: Simulate Corporate Inbound Responses via Mock Company Agent
    class DummyCtx:
        async def send(self, _, msg):
            pass

    dummy_ctx = DummyCtx()

    batch_reqs = [r for r in reqs if r.get("batch_id") == batch_id]
    if not batch_reqs:
        batch_reqs = reqs

    # 5a. Swiggy sends ACK with Ticket
    swiggy_req = next((r for r in batch_reqs if "swiggy" in r["company_name"].lower()), None)
    if swiggy_req:
        print("\n[*] [MOCK COMPANY]: Swiggy replies with formal ACK + Ticket Reference...")
        ack_inbound = InboundReply(
            session_id=swiggy_req.get("session_id"),
            batch_id=swiggy_req.get("batch_id"),
            request_id=swiggy_req["request_id"],
            company_name="Swiggy",
            from_email="grievance@swiggy.in",
            subject="Acknowledgment of Erasure Request [Ref: SWIGGY-DPDP-8821]",
            body=SWIGGY_ACK_BODY,
            received_at=now_iso(),
        )
        await handle_inbound_reply(dummy_ctx, "mock_company", ack_inbound)

    # 5b. Zomato sends PARTIAL with Tax retention
    zomato_req = next((r for r in batch_reqs if "zomato" in r["company_name"].lower()), None)
    if zomato_req:
        print("[*] [MOCK COMPANY]: Zomato replies with PARTIAL resolution (Income Tax Act exemption)...")
        zom_inbound = InboundReply(
            session_id=zomato_req.get("session_id"),
            batch_id=zomato_req.get("batch_id"),
            request_id=zomato_req["request_id"],
            company_name="Zomato",
            from_email="grievance@zomato.com",
            subject="Resolution of Erasure Request [Ref: ZOMATO-DPDP-4412]",
            body=ZOMATO_PARTIAL_BODY,
            received_at=now_iso(),
        )
        await handle_inbound_reply(dummy_ctx, "mock_company", zom_inbound)

    # 5c. Swiggy completes full erasure
    if swiggy_req:
        print("[*] [MOCK COMPANY]: Swiggy confirms 100% complete data erasure (RESOLVED)...")
        res_inbound = InboundReply(
            session_id=swiggy_req.get("session_id"),
            batch_id=swiggy_req.get("batch_id"),
            request_id=swiggy_req["request_id"],
            company_name="Swiggy",
            from_email="grievance@swiggy.in",
            subject="Confirmation of Erasure [Ref: SWIGGY-DPDP-8821]",
            body=SWIGGY_RESOLVED_BODY,
            received_at=now_iso(),
        )
        await handle_inbound_reply(dummy_ctx, "mock_company", res_inbound)

    # Step 6: Advance Demo Clock by 31 Days (Paytm was silent -> Overdue)
    print("\n⏩ ADVANCING DEMO CLOCK BY 31 DAYS (Testing 30-Day Statutory Deadline Expiration)...")
    clock.advance_days(31)
    print(f"[*] Simulated Time Now: {now().strftime('%Y-%m-%d %H:%M:%S UTC')}")
    await sweep_deadlines(dummy_ctx)

    paytm_req = next((r for r in repo.get_all_open_requests() if "paytm" in r["company_name"].lower()), None)
    if paytm_req:
        print(f"[!] Paytm Request State after 31 Days: `{paytm_req['state']}` (Follow-up notice dispatched)")

    # Step 7: Advance Demo Clock by another 31 Days (Paytm still silent -> Escalation Drafted)
    print("\n⏩ ADVANCING DEMO CLOCK BY ANOTHER 31 DAYS (Testing Grievance Exhaustion & Section 13(3) Escalation)...")
    clock.advance_days(31)
    print(f"[*] Simulated Time Now: {now().strftime('%Y-%m-%d %H:%M:%S UTC')}")
    await sweep_deadlines(dummy_ctx)

    paytm_req_final = repo.get_request(paytm_req["request_id"]) if paytm_req else {}
    print(f"[!] Paytm Final State: `{paytm_req_final.get('state')}` (Grievance Redressal Exhausted)")

    # Step 8: User inspects STATUS in ASI:One
    print("\n>>> [USER CHAT]: 'STATUS'")
    status_msg = ChatMessage(
        timestamp=int(now().timestamp()),
        msg_id=uuid4(),
        content=[TextContent(type="text", text="STATUS")],
    )
    await send_ack(user_ctx, user_addr, status_msg)
    await handle_chat_message(user_ctx, user_addr, status_msg)

    # Step 9: User inspects DEBUG trace in ASI:One
    print(">>> [USER CHAT]: 'DEBUG'")
    debug_msg = ChatMessage(
        timestamp=int(now().timestamp()),
        msg_id=uuid4(),
        content=[TextContent(type="text", text="DEBUG")],
    )
    await send_ack(user_ctx, user_addr, debug_msg)
    await handle_chat_message(user_ctx, user_addr, debug_msg)

    print("=" * 80)
    print("   DEMO COMPLETED SUCCESSFULLY IN ~5 SECONDS")
    print("   Swiggy: RESOLVED | Zomato: PARTIAL (Tax Exemption) | Paytm: ESCALATION DRAFTED")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(run_full_demo())
