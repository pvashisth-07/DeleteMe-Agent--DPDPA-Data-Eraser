# Verified API and Protocol Notes

This document contains verified imports, schemas, endpoints, and usage patterns for Fetch.ai uAgents, ASI:One, MCP, and DPDPA tooling.

---

## 1. Agent Chat Protocol (ACP)

### Module & Imports
Available in `uagents-core` (`uagents_core.contrib.protocols.chat`):
```python
from uagents_core.contrib.protocols.chat import (
    ChatMessage,
    ChatAcknowledgement,
    TextContent,
    MetadataContent,
    ResourceContent,
    StartSessionContent,
    EndSessionContent,
    chat_protocol_spec,
)
```

### Protocol Initialization
```python
from uagents import Protocol

chat_proto = Protocol(spec=chat_protocol_spec)

# Inclusion in agent (manifest publishing is required for ASI:One discoverability)
agent.include(chat_proto, publish_manifest=True)
```

### ACP Core Invariants
1. **Always Acknowledge First**: When receiving a `ChatMessage`, immediately respond with a `ChatAcknowledgement`:
   ```python
   await ctx.send(
       sender,
       ChatAcknowledgement(
           timestamp=int(now().timestamp()),
           acknowledged_msg_id=msg.msg_id,
           metadata={}
       )
   )
   ```
2. **Text Reply**:
   ```python
   await ctx.send(
       sender,
       ChatMessage(
           timestamp=int(now().timestamp()),
           msg_id=uuid4(),
           content=[TextContent(type="text", text="Your response message here")]
       )
   )
   ```

---

## 2. Interactive Cards in ASI:One

ASI:One supports rich interactive cards passed via `MetadataContent` in the `ChatMessage` content array alongside `TextContent` (for full graceful degradation).

### Card Structure Schema
```python
MetadataContent(
    type="metadata",
    metadata={
        "card_protocol_version": "1",
        "card_kind": "review",  # "confirmation" | "review" | "status" | "reply"
        "requires_card_interaction": True,
        "card_payload": {
            "title": "Review Your DPDPA Deletion Requests",
            "batch_id": "batch_12345",
            "companies": [
                {
                    "name": "Swiggy",
                    "recipient": "grievance@swiggy.in",
                    "verified": True,
                    "subject": "Erasure Request under Section 12, DPDPA 2023",
                    "preview": "Pursuant to Section 12 of the Digital Personal Data Protection Act, 2023..."
                }
            ],
            "actions": [
                {"label": "Approve All", "command": "APPROVE batch_12345", "style": "primary"},
                {"label": "Cancel", "command": "CANCEL", "style": "danger"}
            ]
        }
    }
)
```
- Interactive card button clicks translate directly into inbound user `ChatMessage` text strings (e.g. `APPROVE batch_12345`).
- Both Card and Plain-Text fallback are always provided.

---

## 3. Payment Protocol

### Module & Imports
Available in `uagents-core` (`uagents_core.contrib.protocols.payment`):
```python
from uagents_core.contrib.protocols.payment import (
    RequestPayment,
    CommitPayment,
    CompletePayment,
    RejectPayment,
    CancelPayment,
    Funds,
    payment_protocol_spec,
)
```

### Models & Attributes
- **`Funds`**:
  - `amount: str` (e.g. `"1000000000000000"`)
  - `currency: str` (e.g. `"atestfet"`)
  - `payment_method: str` (e.g. `"native"` or `"stripe"`)
- **`RequestPayment`**:
  - `accepted_funds: list[Funds]`
  - `recipient: str` (Agent address / wallet)
  - `deadline_seconds: int`
  - `reference: str` (Batch ID or lookup ID)
  - `description: str`
  - `metadata: dict`
- **`CommitPayment`**:
  - `funds: Funds`
  - `recipient: str`
  - `transaction_id: str`
  - `reference: str`
  - `description: str`
  - `metadata: dict`
- **`CompletePayment`**:
  - `transaction_id: str`

---

## 4. ASI:One LLM API

- **Base URL**: `https://api.asi1.ai/v1`
- **Model**: `asi1` (fallback: `asi1-mini`)
- **Client**: Standard `openai.AsyncOpenAI` client
```python
from openai import AsyncOpenAI

client = AsyncOpenAI(
    base_url=os.getenv("ASI1_BASE_URL", "https://api.asi1.ai/v1"),
    api_key=os.getenv("ASI1_API_KEY", "mock-key"),
)
```
- **JSON Structured Output**: Handled via schema-prompt injection and response format `{ "type": "json_object" }` with 1 automated self-repair retry on pydantic validation failure.

---

## 5. Model Context Protocol (MCP)

- **Library**: `mcp==2.3.0`
- **Server Import**: `from mcp.server.mcpserver import MCPServer`
- **Exposed Tools**:
  - `find_grievance_contact(company: str) -> dict`
  - `draft_erasure_request(company: str, user_profile: dict) -> dict`

---

## 6. Agent Funding & Agentverse Mailbox
- **Faucet helper**:
  ```python
  from uagents.setup import fund_agent_if_low
  fund_agent_if_low(agent.wallet.address())
  ```
- **Mailbox initialization**:
  ```python
  agent = Agent(
      name="deleteme_concierge",
      seed=os.getenv("CONCIERGE_SEED"),
      mailbox=True,
      publish_agent_details=True
  )
  ```
