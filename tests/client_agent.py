import asyncio
import sys
from pathlib import Path
from typing import Any
from uuid import uuid4

# Ensure project root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from uagents import Agent, Context
from uagents.setup import fund_agent_if_low
from uagents_core.contrib.protocols.chat import (
    ChatAcknowledgement,
    ChatMessage,
    StartSessionContent,
    TextContent,
)

from agents.concierge.agent import concierge_agent
from shared.acp import build_chat_protocol
from shared.clock import now
from shared.logging import setup_logger

logger = setup_logger("client_agent")

client = Agent(
    name="test_client_agent",
    seed="test_client_agent_seed_phrase_demo",
    port=8002,
    endpoint=["http://127.0.0.1:8002/submit"],
)

received_messages = []
received_acks = []


async def handle_client_reply(ctx: Context, sender: str, msg: ChatMessage):
    for item in msg.content:
        if isinstance(item, TextContent) or hasattr(item, "text"):
            text = getattr(item, "text", "")
            print(f"\n[CLIENT RECEIVED REPLY from {sender[:12]}...]:\n{text}\n")
            received_messages.append(text)


async def on_ack(ctx: Context, sender: str, msg: ChatAcknowledgement):
    print(f"\n[CLIENT RECEIVED ACK] for msg_id={msg.acknowledged_msg_id} at ts={msg.timestamp}")
    received_acks.append(msg)


chat_proto = build_chat_protocol(handle_client_reply, on_ack=on_ack)
client.include(chat_proto, publish_manifest=False)


@client.on_event("startup")
async def on_startup(ctx: Context):
    fund_agent_if_low(client.wallet.address())
    concierge_addr = concierge_agent.address
    print(f"[*] Client Agent {client.address} started.")
    print(f"[*] Sending initial deletion request to Concierge ({concierge_addr})...")

    initial_msg = ChatMessage(
        timestamp=int(now().timestamp()),
        msg_id=uuid4(),
        content=[
            StartSessionContent(),
            TextContent(type="text", text="Delete me from Swiggy, Zomato and Paytm"),
        ],
    )
    await ctx.send(concierge_addr, initial_msg)


async def run_roundtrip_test():
    """Runs in-memory direct test without needing background ports."""
    from agents.concierge.agent import handle_chat_message
    from shared.acp import send_ack

    print("=" * 60)
    print("   DeleteMe Concierge Agent - Client Round-Trip Verification")
    print("=" * 60)

    # Mock context to record replies
    class MockContext:
        def __init__(self):
            self.replies = []
            self.acks = []

        async def send(self, recipient: str, msg: Any):
            if isinstance(msg, ChatAcknowledgement):
                self.acks.append(msg)
                print(f"[ACK RECEIVED] Msg ID: {msg.acknowledged_msg_id}")
            elif isinstance(msg, ChatMessage):
                self.replies.append(msg)
                for c in msg.content:
                    if hasattr(c, "text"):
                        print(f"\n[CONCIERGE REPLY TO USER]:\n{c.text}\n")

    mock_ctx = MockContext()
    test_sender = "agent1q_test_client_user_address"

    # Turn 1: User says: "Delete me from Swiggy, Zomato and Paytm"
    turn1_msg = ChatMessage(
        timestamp=int(now().timestamp()),
        msg_id=uuid4(),
        content=[
            StartSessionContent(),
            TextContent(type="text", text="Delete me from Swiggy, Zomato and Paytm"),
        ],
    )

    # Step 1: Send Ack
    await send_ack(mock_ctx, test_sender, turn1_msg)
    # Step 2: Handle message
    await handle_chat_message(mock_ctx, test_sender, turn1_msg)

    assert len(mock_ctx.acks) >= 1, "Failed: Concierge did not send acknowledgement"
    assert len(mock_ctx.replies) >= 1, "Failed: Concierge did not send reply"

    first_reply = mock_ctx.replies[-1].content[0].text
    assert "Swiggy" in first_reply and "Zomato" in first_reply and "Paytm" in first_reply
    assert "full name" in first_reply or "email address" in first_reply

    print("[+] TURN 1 VERIFIED: Concierge acknowledged, identified 3 companies, and prompted for missing identity.")

    # Turn 2: User provides identity: "My name is Aarav Sharma and email is aarav@example.com"
    turn2_msg = ChatMessage(
        timestamp=int(now().timestamp()),
        msg_id=uuid4(),
        content=[
            TextContent(type="text", text="My name is Aarav Sharma, email is aarav@example.com"),
        ],
    )
    await send_ack(mock_ctx, test_sender, turn2_msg)
    await handle_chat_message(mock_ctx, test_sender, turn2_msg)

    second_reply = mock_ctx.replies[-1].content[0].text
    assert "Aarav Sharma" in second_reply
    assert "aarav@example.com" in second_reply
    assert "YES" in second_reply

    print("[+] TURN 2 VERIFIED: Identity attached, confirmation requested with 'YES' prompt.")

    # Turn 3: User replies "YES"
    turn3_msg = ChatMessage(
        timestamp=int(now().timestamp()),
        msg_id=uuid4(),
        content=[TextContent(type="text", text="YES")],
    )
    await send_ack(mock_ctx, test_sender, turn3_msg)
    await handle_chat_message(mock_ctx, test_sender, turn3_msg)

    third_reply = mock_ctx.replies[-1].content[0].text
    assert "Confirmed" in third_reply or "Batch ID" in third_reply

    print("[+] TURN 3 VERIFIED: Confirmed state reached, batch ID created.")
    print("=" * 60)
    print("ALL CONCIERGE ACP ROUND-TRIP TESTS PASSED!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(run_roundtrip_test())
