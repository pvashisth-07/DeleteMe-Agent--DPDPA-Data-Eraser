# DeleteMe Architecture Specification

The **DeleteMe DPDPA Rights Agent** is an autonomous multi-agent decentralized privacy infrastructure engineered on **Fetch.ai uAgents**, **ASI:One**, and the **Model Context Protocol (MCP)**.

---

## 1. System Multi-Agent Flow

```mermaid
sequenceDiagram
    autonumber
    actor User as Data Principal (in ASI:One)
    participant Concierge as Concierge Agent
    participant Registry as Agentverse Almanac
    participant Discovery as Discovery Specialist
    participant Drafter as Drafter Specialist
    participant MCP as MCP Server
    participant Dispatcher as Dispatcher Agent
    participant Tracker as Tracker Agent
    participant Fiduciary as Data Fiduciary (Mock Company)

    User->>Concierge: "Delete me from Swiggy, Zomato and Paytm" (via ACP)
    Concierge-->>User: ChatAcknowledgement (Instant)
    Concierge->>User: Request name and email for statutory verification
    User->>Concierge: "Aarav Sharma, aarav@example.com"
    Concierge->>Registry: Lookup addresses for Discovery & Drafter
    Concierge->>Discovery: Fan-Out DiscoveryRequest(Swiggy, Zomato, Paytm)
    Discovery->>MCP: find_grievance_contact(company)
    MCP-->>Discovery: Contact info + verified flag
    Discovery-->>Concierge: Fan-In DiscoveryResult
    Concierge->>Drafter: Fan-Out DraftRequest per contact
    Drafter->>MCP: draft_erasure_request(company, user_profile)
    MCP-->>Drafter: Legal draft + SHA256 content hash
    Drafter-->>Concierge: Fan-In DraftResult
    Concierge->>User: Interactive Review Card / Fallback Text
    User->>Concierge: "APPROVE <batch_id>"
    Concierge->>Dispatcher: DispatchRequest (with HMAC approval token & payment ref)
    Dispatcher->>Dispatcher: Verify HMAC token & Content Hash
    Dispatcher->>Fiduciary: SMTP Send (plus-addressed Reply-To)
    Dispatcher-->>Concierge: DispatchResult (SENT)
    Concierge->>Tracker: TrackRequest (sent_at, deadline_at = +30 days)
    Tracker->>Tracker: on_interval sweep / on_event classification
    Fiduciary-->>Tracker: InboundReply
    Tracker->>Concierge: StatusUpdate (RESOLVED / PARTIAL / OVERDUE)
    Concierge->>User: Proactive chat notification
```

---

## 2. External MCP Client Integration Guide

The DeleteMe system provides a standalone **Model Context Protocol (MCP)** server at `mcp/server.py` that can be queried by external AI assistants like **Claude Desktop**, **Cursor**, or custom MCP clients.

### Available MCP Tools
1. **`find_grievance_contact`**:
   - Argument: `company` (string, e.g. `"Swiggy"`)
   - Output: Grievance Officer name, email, verified status, source policy URL.
2. **`draft_erasure_request`**:
   - Arguments: `company` (string), `user_profile` (object with `name`, `email`, `phone`, `identifiers`)
   - Output: Legally formatted DPDPA Section 12 erasure request, verified status, and SHA-256 hash.

### Configuring Claude Desktop (`claude_desktop_config.json`)
```json
{
  "mcpServers": {
    "deleteme-dpdpa": {
      "command": "python",
      "args": ["-m", "mcp.server"],
      "cwd": "D:\\FetchAThon"
    }
  }
}
```

### Configuring Cursor (`.cursor/mcp.json`)
```json
{
  "mcpServers": {
    "deleteme-dpdpa": {
      "command": "python",
      "args": ["-m", "mcp.server"],
      "cwd": "${workspaceFolder}"
    }
  }
}
```

---

## 3. Cryptographic Invariants & Security Gating
1. **HMAC-SHA256 Token**:
   - `content_hash = sha256(canonical_json(drafts))`
   - `token = HMAC(APPROVAL_HMAC_SECRET, batch_id + session_id + content_hash)`
   - Any manual `EDIT` or `REMOVE` modifies the content hash, instantly invalidating previous approval tokens.
2. **Prohibited PII Defense**:
   - The Drafter agent and MCP tools reject any draft containing 12-digit Aadhaar numbers, PAN numbers, OTPs, or passwords with an immediate `ValueError`.
