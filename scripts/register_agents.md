# Agentverse Registration & ASI:One Discoverability Guide

This guide describes how to register the **DeleteMe Concierge** and specialist agents on **Agentverse** and make them discoverable and usable inside **ASI:One**.

---

## 1. Prerequisites
- An active account on [Agentverse](https://agentverse.ai/)
- An account on [ASI:One](https://asi1.ai/)
- Your API Key from Agentverse (`AGENTVERSE_API_KEY`) and Mailbox Key (`AGENT_MAILBOX_KEY`)

---

## 2. Agent Deterministic Addresses

Each agent in DeleteMe uses a distinct deterministic seed configured in `.env`:

| Agent Name | Config Seed Variable | Agentverse Address | Role |
|---|---|---|---|
| **Concierge** | `CONCIERGE_SEED` | `agent1qfq66d3thuzjl620d06sqn88j0ey650up6ltwt46qhljraz2fe4g50yap2z` | Primary conversational chat agent in ASI:One |
| **Discovery** | `DISCOVERY_SEED` | `agent1qtsk8vqfdywqg89mswxg29dpeftnnxq6jvmp0yphv9z5vcl67fgrjdsdnqg` | Policy scraper & Rule 9 Grievance Officer locator |
| **Drafter** | `DRAFTER_SEED` | `agent1q0su27nruzqk75kpwdtese6k083lde3lzj2aw5yawfw00y9d9u6kcffus6l` | DPDPA Section 12 legal notice compiler |
| **Dispatcher** | `DISPATCHER_SEED` | `agent1qwmqhv5ll2fswhhvfxtzywfsxew2a3ufln2tsj8vzkzdktd789tpw7cmmup` | Verified SMTP dispatcher with HMAC guard |
| **Tracker** | `TRACKER_SEED` | `agent1qfs4f9apm6hg066577z8t2my673s9d0gcx2jjafeatujvpcpgr2ag9swpsd` | 30-day lifecycle tracker & reply classifier |
| **Mock Company** | `MOCK_COMPANY_SEED` | `agent1qwhk3gqawq5auzsddt44mt77wrr8078yvzexp9l35cq22vymfus3qex5je4` | Simulated test company for demo scenarios |

---

## 3. Step-by-Step Mailbox Agent Registration

### Step A: Generate Mailbox Key
1. Log into **Agentverse** -> Navigate to **My Agents** -> Click **+ New Agent**.
2. Select **Mailbox Agent** (local runner).
3. Name the agent `deleteme_concierge`.
4. Copy the generated **Mailbox Key** and paste it into `.env`:
   ```bash
   AGENT_MAILBOX_KEY=your_mailbox_key_here
   ```

### Step B: Configure Profile & Badges
1. Open the agent inspector on Agentverse.
2. Click on **Agent Details** / **Profile**.
3. Set Agent Name: `DeleteMe DPDPA Rights Concierge`
4. Copy the exact markdown from [`agents/concierge/README.md`](../agents/concierge/README.md) and paste it into the **Description / README** editor.
5. Verify both badges render correctly:
   - `![tag:innovationlab](https://img.shields.io/badge/innovationlab-3D8BD3)`
   - `![tag:hackathon](https://img.shields.io/badge/hackathon-5F43F1)`

### Step C: Tags & Discovery Keywords
Under the agent's **Discovery / Search Tags** section, add:
- `innovationlab`
- `hackathon`
- `dpdpa`
- `privacy`
- `chat`
- `india`
- `deleteme`

### Step D: Agent Chat Protocol (ACP) Manifest
Ensure **Publish Manifest** is enabled (`publish_manifest=True` in code). This publishes the `AgentChatProtocol:0.3.0` specification to the Agentverse Almanac, allowing ASI:One to route chat sessions directly to the agent.

---

## 4. MCP-Automated Registration Path (If MCP is Connected)

If your environment is connected to the Agentverse MCP Server (`https://mcp.agentverse.ai/sse`):
1. In your AI IDE prompt:
   ```text
   Register local agent with address agent1qfq66d3thuzjl620d06sqn88j0ey650up6ltwt46qhljraz2fe4g50yap2z using the description from agents/concierge/README.md and tags 'innovationlab', 'hackathon'.
   ```
2. The MCP tool `create_or_update_agent` will automatically register the profile and Almanac records.

---

## 5. Testing & Verification in ASI:One

1. Start the concierge agent locally:
   ```bash
   python -m agents.concierge.agent
   ```
2. Open [ASI:One](https://asi1.ai/) in your browser.
3. In the search bar or agent selector, type `DeleteMe` or search by address:
   `agent1qfq66d3thuzjl620d06sqn88j0ey650up6ltwt46qhljraz2fe4g50yap2z`
4. Start a conversation with:
   *"Delete me from Swiggy, Zomato and Paytm"*
5. Confirm the agent sends back an acknowledgement and replies asking for your name and email.
6. Take a screenshot and place it in `docs/asi1_chat_proof.png` (or record the URL in `docs/deployment.md`).
