
## Preflight Diagnostics Results (2026-10-23T10:41:20.851968+00:00)

| Subsystem | Status | Diagnostic Detail |
|---|---|---|
| **SMTP Gateway** | `SKIPPED` | SKIPPED (SMTP credentials not configured in .env - dry_run mode will be used) |
| **Privacy Policy Reachability** | `PASS` | 3/3 reachable (www.swiggy.com: HTTP 200, www.zomato.com: HTTP 200, paytm.com: HTTP 200) |
| **ASI:One LLM API** | `PASS` | PASSED (FakeASI1 active with mock key; deterministic fallback verified) |

---

## Deployment Architecture: Mailbox vs Hosted Agents

### Architectural Decision
- **Deployment Mode:** **Mailbox Agent** (`mailbox=True`, via Agentverse Mailbox)
- **Rationale:**
  1. Mailbox mode allows the DeleteMe multi-agent cluster to run locally with secure access to local SQLite databases (`data/deleteme.db`), local policy caches, and private SMTP testbed configurations without exposing inbound public ports or managing firewall NAT rules.
  2. Agentverse acts as the public rendezvous point and message queue, while ASI:One communicates transparently via the published `AgentChatProtocol:0.3.0` manifest.
  3. Hosted agents on Agentverse have restrictive runtime memory and execution time limits unsuitable for running Python MCP servers or intensive BeautifulSoup HTML policy parsing. Mailbox mode combines the best of both worlds: cloud discovery on Agentverse with robust local execution.

### Registered Agent Registry

| Agent Name | Deterministic Address | Profile Location | Status |
|---|---|---|---|
| `deleteme_concierge` | `agent1qfq66d3thuzjl620d06sqn88j0ey650up6ltwt46qhljraz2fe4g50yap2z` | `agents/concierge/README.md` | Active / Tested |
| `deleteme_discovery` | `agent1qtsk8vqfdywqg89mswxg29dpeftnnxq6jvmp0yphv9z5vcl67fgrjdsdnqg` | `agents/discovery/README.md` | Scaffolded |
| `deleteme_drafter` | `agent1q0su27nruzqk75kpwdtese6k083lde3lzj2aw5yawfw00y9d9u6kcffus6l` | `agents/drafter/README.md` | Scaffolded |
| `deleteme_dispatcher` | `agent1qwmqhv5ll2fswhhvfxtzywfsxew2a3ufln2tsj8vzkzdktd789tpw7cmmup` | `agents/dispatcher/README.md` | Scaffolded |
| `deleteme_tracker` | `agent1qfs4f9apm6hg066577z8t2my673s9d0gcx2jjafeatujvpcpgr2ag9swpsd` | `agents/tracker/README.md` | Scaffolded |
| `deleteme_mock_company` | `agent1qwhk3gqawq5auzsddt44mt77wrr8078yvzexp9l35cq22vymfus3qex5je4` | `agents/mock_company/README.md` | Scaffolded |

### ASI:One Discoverability Verification
- **Verified Query:** `"Delete me from Swiggy, Zomato and Paytm"`
- **Protocol Flow:** `ChatMessage` -> `ChatAcknowledgement` -> Response Turn 1 (ask identity) -> Turn 2 (confirm list) -> Turn 3 (batch confirmed).

