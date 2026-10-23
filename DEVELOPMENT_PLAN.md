# DeleteMe Agent (DPDPA Rights Agent): Phase-by-Phase Development Plan

> **How to use this file with Antigravity:** paste the **Master Prompt** (the full MISSION spec) once as standing context, then feed **one phase at a time** using the "Prompt for Antigravity" block at the end of each phase. Do not start a phase until the previous phase's **Exit Gate** passes. Each phase ends in a runnable, tested state and a git commit.

---

## 0. Ground Truth Checked Against the Sources

### From the Fetch-a-thon 3.0 hackpack (innovationlab.fetch.ai/.../fetch-a-thon-3/hackpack)

| Item | Fact | Impact on plan |
|---|---|---|
| Hackathon day | **Sat 24 Oct 2026**. Building 10:30, **final submission 16:30 IST**, closing 17:50 | Only **~6 hours of on-site build time**. Phases 0–2 should be done (or at least scaffolded) **before** the event, if the rules allow pre-work. Otherwise follow the MVP cut line in §3. |
| Mandatory | ≥1 agent on Agentverse, ACP, discoverable and usable in ASI:One, tool use or multi-agent orchestration, whole primary workflow inside **one** ASI:One conversation, public GitHub repo with run/test instructions | Phases 1–3 deliver every mandatory item |
| Bonus | Multi-agent collaboration, **Payment Protocol with a credible monetization model**, **Interactive Cards**, error handling and recovery, real-time data, an agent that keeps running after the event | Phases 4–7 |
| ACP | `uagents_core.contrib.protocols.chat`: `ChatMessage`, `ChatAcknowledgement`, `TextContent`, `StartSessionContent`, `EndSessionContent`, `chat_protocol_spec`; `Protocol(spec=chat_protocol_spec)`; always ack first; `agent.include(chat_proto, publish_manifest=True)` | Shared ACP helper in Phase 1 |
| Funding | `uagents.setup.fund_agent_if_low` | Call on startup of every agent |
| Agentverse MCP | Full: `https://mcp.agentverse.ai/sse`; Lite: `https://mcp-lite.agentverse.ai/mcp` | Phase 2 registration |
| Versions | **The hackpack pins no versions** for `uagents` / `uagents-core`, and its ACP snippet is incomplete (missing imports, broken indentation) | Phase 0: pin the versions that are actually installed, and copy patterns from `fetchai/innovation-lab-examples`, not from the hackpack snippet |
| ASI:One API | The hackpack gives no base URL or model name. It links to the ASI:One quickstart | Phase 0: read the quickstart and put the values in `.env.example` and ASSUMPTIONS.md |
| Submission | Public **ASI:One shared chat URL**, **Agentverse profile URL for each agent**, public GitHub repo, **3–5 min demo video**, short description (problem, users, outcome) | Phase 10 checklist |
| README | Name and address of every agent, extra resources with links, both badges on every agent | Phases 2 and 10 |
| Judging | Functionality 25%, Fetch.ai tech 20%, Innovation 20%, Impact 20%, UX/presentation 15% | Evidence table in Phase 10 |
| Side prizes | Best Multi-Agent Workflow, Best Agentverse Deployment, Best Personal AI | The architecture targets all three |

### From dpdpa.com

| Item | Fact | Impact on plan |
|---|---|---|
| Act structure | Ch.3 (ss.11–15): s.11 access, **s.12 correction and erasure**, **s.13 grievance redressal**, s.14 nominate, s.15 duties. Ch.5 (ss.18–26): Data Protection Board | Legal templates in `config/law.yaml` |
| Enforcement (G.S.R. 843(E)) | **On publication**: s.1(2), s.2, **ss.18–26 (Board)**, 35, 38–43, 44(1),(3). **+1 year**: s.6(9), s.27(1)(d). **+18 months**: ss.3–5, 6(1)–(8),(10), 7–10, **ss.11–17 (rights)**, 27 (except (1)(d)), 28–34, 36, 37, 44(2) | Drafts must use **pre-commencement "good faith" wording** by default (`LAW_IN_FORCE=false`) |
| Rules mapping | dpdpa.com maps s.11 → **Rule 14 "Rights of Data Principals"**, s.8 → Rules 6–9 (**Rule 9: contact information of the person who answers questions about processing**), s.27 → **Rule 20 (Board as digital office)**. **No rule is mapped to ss.12, 13 or 14 on that page** | Cite as "DPDP Rules 2025 (Rights of Data Principals)" without a rule number. Discovery looks for the Rule 9 contact |
| Response deadline | **dpdpa.com states no response period** for grievances or rights requests | `RESPONSE_DEADLINE_DAYS` stays configurable (default 30) with `TODO: verify against https://dpdpa.com/DPDP_Rules_2025_English_only.pdf` |
| Primary sources | Act PDF: https://dpdpa.com/DPDPA_2023_official.pdf · Rules PDF: https://dpdpa.com/DPDP_Rules_2025_English_only.pdf · s.12: https://dpdpa.com/dpdpa2023/chapter-3/section12.html · s.13: https://dpdpa.com/dpdpa2023/chapter-3/section13.html | Link these in `docs/legal_notes.md` |

> **Spec note:** the hackpack lists Interactive Cards and Payment Protocol as **bonus** items, while the Master Prompt marks them required. This plan keeps them required, but schedules them **after** the mandatory core so that a time overrun never puts the mandatory items at risk.

---

## 1. Phase Overview

| # | Phase | Main output | Mandatory or bonus | Suggested time budget (event day) |
|---|---|---|---|---|
| 0 | Environment, research and scaffold | Repo skeleton, `shared/`, config, preflight, FakeASI1 | Foundation | Pre-event (or 30 min) |
| 1 | Concierge + ACP + ASI1 intent | Chat agent that extracts companies and identity | **Mandatory** | Pre-event (or 45 min) |
| 2 | Agentverse registration + ASI:One discoverability | Concierge live in ASI:One; profile README | **Mandatory** | 20 min |
| 3 | Specialist agents: discovery, drafter + MCP + dynamic lookup | Fan-out/fan-in with typed messages | **Mandatory** (orchestration) | 60 min |
| 4 | Review and approval gate + Interactive Cards | HMAC approval token, cards, text fallback | Core safety + bonus | 45 min |
| 5 | Dispatcher + SMTP send modes | dry_run / demo_redirect / live | Core | 40 min |
| 6 | Payment Protocol | User fee gate + agent-to-agent micro-payments | Bonus (required by spec) | 40 min |
| 7 | Tracker + mock_company + demo clock + escalation | State machine, classification, escalation | Core + impact | 60 min |
| 8 | STATUS / DEBUG / proactive updates / IMAP | Observability and UX polish | UX + extra credit | 30 min |
| 9 | Hardening + full test suite + failure paths | All tests green | Reliability extra credit | 30 min |
| 10 | Docs, README evidence table, demo, submission | Submission package | **Mandatory** | 40 min |

**Dependency chain:** 0 → 1 → 2 → 3 → 4 → 5 → (6 ∥ 7) → 8 → 9 → 10. Phases 6 and 7 touch separate files and can run in parallel if two people are building.

---

## 2. Global Conventions (apply in every phase)

- **Python 3.11+**, `uagents`, `uagents-core`, `pydantic` v2, `httpx`, `beautifulsoup4`, `tenacity`, `python-dotenv`, `pyyaml`, `openai` (OpenAI-compatible ASI1 client), `mcp` (Python MCP SDK), `pytest`, `pytest-asyncio`. **No frontend, no FastAPI, no Postgres, no React.**
- Every agent gets its own `*_SEED` env var, and calls `fund_agent_if_low` on startup.
- Every inter-agent message carries `session_id` and `batch_id` (plus `request_id` where relevant) so fan-in can be correlated.
- Every ASI1 call goes through `shared/asi1_client.py`: JSON mode → pydantic validation → **one repair retry** → graceful fallback. Rate-limit and 5xx errors use tenacity backoff. `FakeASI1` is used in all tests.
- Persistence goes through `shared/db.py` (SQLite locally, with a `ctx.storage` adapter for hosted agents).
- Time **only** comes from `shared/clock.py` (`now()` honours `DEMO_CLOCK_SPEED`). Never call `datetime.now()` directly.
- Legal wording **only** comes from `config/law.yaml`. Prices **only** come from `config/pricing.yaml`.
- Never log or commit secrets. `.env.example` lists every variable.
- Log every ambiguity you resolve in **ASSUMPTIONS.md** (date, decision, reason).
- Each phase ends with: `make test` green → `git commit -m "phase N: ..."`.

---

## 3. MVP Cut Line (if you are running out of time on 24 Oct)

Priority order. Everything above the line must be in the submission.

1. Concierge with ACP + ASI1, registered on Agentverse and usable in ASI:One (Phases 1–2)
2. Discovery + drafter as separate uAgents with typed messages (Phase 3, MCP optional)
3. Text-based approval gate with HMAC token (Phase 4, without cards)
4. Dispatcher in `demo_redirect` mode (Phase 5)
5. Tracker with demo clock and the Paytm escalation scenario (Phase 7)
6. README with badges, addresses and evidence table, plus demo video (Phase 10)

**──── MVP line ────**

7. Interactive Cards (Phase 4b)
8. Payment Protocol (Phase 6). If time is short, implement it with `PAYMENTS_BYPASS_FOR_DEMO=true` as a documented fallback, but keep the request/confirm messages real
9. MCP server in the live path (Phase 3b)
10. IMAP poller, ACP on the specialist agents, DEBUG trace polish

---

## PHASE 0: Environment, Research and Scaffold

**Goal:** a reproducible project skeleton with all shared plumbing, verified API access, and nothing agent-specific yet.

### Tasks
1. **Read the docs first** (trust them over memory): hackpack, uAgent creation (including mailbox agents), uAgent-to-uAgent communication, ASI-compatible uAgents, ASI:One overview and quickstart, Interactive Cards, MCP integration, fetch-skills overview, Payment Protocol (search `innovationlab.fetch.ai/resources/docs` and `github.com/fetchai/innovation-lab-examples`). Write findings to `docs/api_notes.md`: exact imports, ASI1 base URL, model name, card schema, payment message models.
2. Install the **fetch-skills CLI** following its overview page. Connect the Agentverse MCP server (`https://mcp.agentverse.ai/sse`) if the IDE supports MCP. Otherwise note "manual registration" in ASSUMPTIONS.md.
3. Create the repo tree exactly as in the Master Prompt (`agents/{concierge,discovery,drafter,dispatcher,tracker,mock_company}`, `mcp/`, `shared/`, `config/`, `data/`, `scripts/`, `tests/{unit,integration,fixtures/policies}`, `docs/`).
4. `pyproject.toml` / `requirements.txt` with **pinned** versions taken from what actually installs. `Makefile` targets: `install`, `test`, `lint`, `preflight`, `run-all`, `demo`.
5. `shared/config.py`: a pydantic-settings style loader for `.env` plus the YAML files.
6. `shared/models.py`: **all** message models from the Master Prompt (`UserProfile`, `DiscoveryRequest/Result`, `DraftRequest/Result`, `DispatchRequest/Result`, `TrackRequest`, `InboundReply`, `StatusUpdate`) plus `session_id` on each, as `uagents.Model` subclasses. Add the internal pydantic schemas used for ASI1 outputs (`IntentExtraction`, `ContactExtraction`, `EmailDraft`, `ReplyClassification`, `EscalationDraft`).
7. `shared/db.py`: a repository interface with tables `sessions`, `batches`, `drafts`, `requests`, `events` (state history), `payments`, `contacts_cache`, `policy_cache`. Implementations: `SqliteRepo` and `CtxStorageRepo`.
8. `shared/asi1_client.py`: `ASI1Client` (OpenAI-compatible, `ASI1_API_KEY`, `ASI1_BASE_URL`, `ASI1_MODEL`), `complete_json(schema, messages)` with the repair retry, `tool_call(...)`, and tenacity retries. Add `FakeASI1` with deterministic canned responses keyed by prompt patterns.
9. `shared/clock.py` (`DemoClock`, `now()`, `days_to_seconds()`), `shared/logging.py` (structured logger plus a trace collector for DEBUG), and a stub `shared/payments.py`.
10. `config/law.yaml`: `RESPONSE_DEADLINE_DAYS: 30  # TODO verify against DPDP Rules 2025 PDF`, `law_in_force: false`, templates `erasure_pre_commencement`, `erasure_post_commencement`, `followup`, `escalation`, `disclaimer: "This is general information, not legal advice."`, and source URLs. **No Board fee anywhere.**
11. `config/pricing.yaml`: `batch_fee`, `discovery_lookup_fee`, `tracking_fee`, `currency`/denomination (testnet only), `bypass_for_demo` default.
12. `data/companies.json`: about 30 Indian consumer apps (Swiggy, Zomato, Paytm, PhonePe, Flipkart, Myntra, Meesho, Ola, Uber India, Rapido, Zepto, Blinkit, BigBasket, Nykaa, MakeMyTrip, Goibibo, IRCTC, BookMyShow, Dream11, MPL, CRED, Groww, Zerodha, Lenskart, Urban Company, Dunzo, JioMart, Ajio, Swiggy Instamart, ShareChat) with `name`, `aliases`, `domain`, `privacy_policy_url`, and **`contact_email: null`**.
13. `scripts/preflight.py`: test (a) SMTP connect plus login (no send), (b) HTTPS GET of 3 policy URLs, (c) a minimal ASI1 completion. Print a PASS/FAIL table and append it to `docs/deployment.md`.
14. `.env.example` with every variable from the spec, plus `ASI1_BASE_URL`, `*_SEED`, `*_ADDR`, `DEBUG_MODE`, `DEMO_CLOCK_SPEED`, `SESSION_TTL_MINUTES`, `APPROVAL_HMAC_SECRET`, `PAYMENTS_BYPASS_FOR_DEMO`, `CONFIRM_LIVE`, `IMAP_*`.
15. Write `ASSUMPTIONS.md`, `LICENSE` (MIT), `.gitignore` (`.env`, `*.db`, `__pycache__`).

### Exit Gate
- `make install && make test` passes (smoke tests for models, db, clock, FakeASI1 JSON repair).
- `python scripts/preflight.py` runs and prints results. Failures are recorded, not fatal.
- `docs/api_notes.md` exists with the verified imports and endpoints.

### Prompt for Antigravity
> Execute PHASE 0 of DEVELOPMENT_PLAN.md. Read every doc URL listed in the Master Prompt first and record exact APIs in docs/api_notes.md. Scaffold the repo, shared modules, configs, companies.json (contact_email null), preflight.py and FakeASI1. Pin dependency versions. Do not write any agent logic yet. Finish when `make test` passes, then commit.

---

## PHASE 1: Concierge Agent with ACP and ASI1 Intent Extraction

**Goal:** a chat agent that receives ACP messages, always acknowledges them, uses ASI1 to extract intent, company names and identity, asks one concise follow-up question if needed, and keeps per-session state.

### Tasks
1. `shared/acp.py`: helpers `make_text_reply(text, end_session=False)`, `send_ack(ctx, sender, msg)`, and a `build_chat_protocol(handler)` factory used by every ACP agent.
2. `agents/concierge/agent.py`: `Agent(name="deleteme_concierge", seed=..., mailbox=True, publish_agent_details=True)` (check the exact flags in the docs). Include the chat protocol with `publish_manifest=True`.
3. `agents/concierge/intent.py`: ASI1 `IntentExtraction` → `{intent: delete|status|approve|edit|remove|cancel|debug|reply_paste|other, companies[], name?, email?, phone?, identifiers{}}`. Run deterministic command parsing (`APPROVE <id>`, `EDIT X: ...`, `REMOVE X`, `CANCEL`, `STATUS`, `DEBUG`, `Reply from X: ...`) **before** calling the LLM.
4. `agents/concierge/session.py`: a state machine `NEW → NEED_IDENTITY → CONFIRM_COMPANIES → DISCOVERING → DRAFTING → AWAITING_APPROVAL → AWAITING_PAYMENT → DISPATCHING → TRACKING | CANCELLED | EXPIRED`. TTL comes from `SESSION_TTL_MINUTES`. Show the disclaimer once per session.
5. A company-confirmation step in plain text for now (the card version comes in Phase 4): "I found: Swiggy, Zomato, Paytm. Reply YES to continue or edit the list."
6. Optional "paste sender names from your promo emails" extraction → candidate list → confirm.
7. `tests/client_agent.py`: a local uAgent that sends `StartSessionContent` + `TextContent` to the concierge and prints the replies.
8. Unit tests: **10 intent prompts** (including messy ones: "pls remove me frm swiggy n zomato", Hinglish, missing email, duplicate companies, unknown company, a status question, an empty message).

### Exit Gate
- `pytest tests/unit/test_intent.py` passes 10/10 with FakeASI1.
- `python tests/client_agent.py` gets an ack and a reply that lists the companies and asks for name and email if they are missing.
- An ASI1 error triggers a retry and then a polite "I'm having trouble thinking right now, please try again" message.

### Prompt for Antigravity
> Execute PHASE 1. Build the concierge uAgent with the Agent Chat Protocol (always ack, publish_manifest=True), deterministic command parser, ASI1 intent extraction with FakeASI1 tests, session state machine with TTL, and tests/client_agent.py. Finish when the 10 intent tests and the client_agent round-trip pass, then commit.

---

## PHASE 2: Agentverse Registration and ASI:One Discoverability

**Goal:** the concierge is live on Agentverse (mailbox agent), has a full profile, and can be found and used inside ASI:One. **This is the first point at which every mandatory hackathon requirement is met.**

### Tasks
1. Run the concierge as a **mailbox agent**. Connect it through the Agentverse inspector or the MCP server.
2. `agents/concierge/README.md` (this is the Agentverse profile): name, one-paragraph description, capabilities, example prompts ("Delete me from Swiggy, Zomato and Paytm", "Status of my deletion requests"), address placeholder, both badges:
   ```
   ![tag:innovationlab](https://img.shields.io/badge/innovationlab-3D8BD3)
   ![tag:hackathon](https://img.shields.io/badge/hackathon-5F43F1)
   ```
3. `scripts/register_agents.md`: exact manual steps (seed → address → mailbox connect → profile README paste → keywords/tags), plus the MCP-automated path if it is available.
4. `scripts/run_all.sh` (and a `run_all.ps1` or Makefile target for Windows): start every agent with `.env` loaded, logs going to `logs/`.
5. Test in ASI:One: search for the agent, send a prompt, confirm the ack and the reply. Record the result (with a screenshot path) in `docs/deployment.md`.

### Exit Gate
- The concierge address is listed in the README. The agent shows up in Agentverse and answers in ASI:One.
- `docs/deployment.md` records the hosted vs mailbox decision and the preflight results.

### Prompt for Antigravity
> Execute PHASE 2. Make the concierge a mailbox agent, write its Agentverse profile README with badges and example prompts, write scripts/register_agents.md and run_all scripts, and document how to verify it in ASI:One. Use the Agentverse MCP server if connected. Commit when done.

---

## PHASE 3: Specialist Agents (Discovery + Drafter), MCP Tools, Dynamic Agent Lookup

**Goal:** real multi-agent orchestration. The concierge looks up the specialists on Agentverse, fans out typed requests in parallel, and fans the results back in.

### 3a. Discovery agent
1. `agents/discovery/agent.py` handles `DiscoveryRequest` → `DiscoveryResult`.
2. Pipeline: alias match in `companies.json` → fetch the policy page with httpx (timeout 8s, polite User-Agent, SQLite cache, fixture fallback in tests) → strip with BeautifulSoup → ASI1 extraction via the MCP tool → `{officer_name, email, address, source_url}`.
3. **`verified=true` only if the email literally appears in the fetched HTML.** Otherwise fall back to `privacy@<domain>` with `verified=false` and the note "UNVERIFIED - please confirm".
4. Unknown company: ASI1 resolves the likely domain → the same pipeline → if that still fails, `error="unknown"` and the concierge asks the user for the email.
5. Look explicitly for the Rule 9 "contact information of a person who can answer questions about processing", grievance officer and DPO sections.
6. Add ACP so it can be used on its own ("find the grievance officer for Swiggy"). Give it a profile README with badges.

### 3b. MCP server
1. `mcp/server.py` (Python MCP SDK) exposes `find_grievance_contact(company)` and `draft_erasure_request(company, user_profile)`.
2. Discovery and drafter call these **through an MCP client** (stdio or HTTP, per the Fetch MCP docs), so MCP is part of the live path.
3. `docs/architecture.md` section: how to connect an external MCP client (Claude Desktop, Cursor, etc.).

### 3c. Drafter agent
1. `DraftRequest` → `DraftResult`. Fill the template from `law.yaml` (pre/post commencement chosen by `law_in_force`). ASI1 only personalises the wording; the legal sentence is fixed text from the template.
2. The body must include the user's name and the identifiers they provided, the s.12 erasure request, a request for a **written list of any data retained, its legal basis and its retention period**, a request for a ticket or reference ID, the response window from config, and the disclaimer. **Never** Aadhaar, PAN, passwords or OTPs (enforced by a regex guard plus a test).
3. Add ACP ("draft a DPDPA erasure request for Zomato") and a profile README with badges.

### 3d. Concierge orchestration
1. `agents/concierge/registry.py`: search Agentverse (by capability keywords plus the innovationlab/hackathon tags) → cache the addresses → fall back to `DISCOVERY_ADDR`, `DRAFTER_ADDR`, `DISPATCHER_ADDR`, `TRACKER_ADDR`. Log which path was used.
2. Parallel fan-out of `DiscoveryRequest` per company, then `DraftRequest` per contact. 10s timeout, tenacity retries, **partial results allowed** (failed companies are listed with a reason).
3. ASI1 tool calling for planning, with tools `discover_company`, `draft_request`, `request_approval`, `send_batch`, `get_status`. If tool calling is not supported, fall back to a deterministic planner and log it in ASSUMPTIONS.md.

### Tests
- Discovery extractor on saved `tests/fixtures/policies/*.html` (at least 1 verified and 1 unverified case).
- Drafter: the pre-commencement wording is present, no forbidden identifiers, the disclaimer is present.
- Discovery timeout → partial results. Agentverse search failure → env fallback used and logged.

### Exit Gate
- `client_agent.py` "Delete me from Swiggy, Zomato and Paytm" + name/email → three drafts returned with verified/unverified flags.
- All three agents are registered and their addresses are in the README.

### Prompt for Antigravity
> Execute PHASE 3. Build discovery and drafter uAgents (typed Models + ACP + profile READMEs), mcp/server.py with find_grievance_contact and draft_erasure_request used via the MCP client path, and the concierge registry (Agentverse search with env fallback) plus parallel fan-out/fan-in with timeouts and partial results. Use saved policy fixtures in tests. Never invent grievance emails. Commit when tests and the client_agent flow pass.

---

## PHASE 4: Review and Approval Gate + Interactive Cards

**Goal:** a human-in-the-loop gate that cannot be bypassed.

### 4a. Gate logic (build first, text only)
1. `shared/approval.py`: `content_hash = sha256(canonical_json(drafts))`; `token = HMAC(APPROVAL_HMAC_SECRET, batch_id + session_id + content_hash)`; `verify(token, batch_id, session_id, drafts)`.
2. Review message per company: recipient, **VERIFIED / UNVERIFIED** badge, subject, body preview, sender address, send mode. Then the command footer: `APPROVE <batch_id> | EDIT <company>: ... | REMOVE <company> | CANCEL | STATUS`.
3. Any `EDIT` or `REMOVE` produces a new content hash and **invalidates** any earlier token. The review is shown again.
4. Session expiry gives a clear message ("This batch expired after N minutes. Nothing was sent. Say 'start again'.").

### 4b. Interactive Cards
1. Follow the card schema from `docs/api_notes.md` (the Interactive Cards docs). Cards: **company confirmation**, **batch review** (one section per company, expandable body, Approve/Edit/Remove/Cancel buttons).
2. Card buttons send the same commands as the text fallback, so there is a single code path and the same token.
3. Always send the plain-text fallback alongside, or when cards are not supported.

### Tests
- An unapproved batch is **never** dispatched. A tampered body (hash mismatch) is rejected. A token from another session is rejected. Edit after approve → the old token is rejected.
- Session expiry test with the fake clock.

### Exit Gate
- Text flow: review → APPROVE → token is issued. The card renders in ASI:One (a screenshot goes in `docs/`).

### Prompt for Antigravity
> Execute PHASE 4. Implement shared/approval.py (HMAC token over batch_id+session_id+content_hash), the review message with VERIFIED/UNVERIFIED badges and command footer, edit/remove invalidation, session expiry, then Interactive Cards (confirmation + review) that map onto the same commands. Add the approval-token unit tests. Commit when green.

---

## PHASE 5: Dispatcher Agent and SMTP Send Modes

**Goal:** emails go out safely. The dispatcher refuses anything that is not approved (and paid, from Phase 6 onward).

### Tasks
1. `agents/dispatcher/agent.py`: accepts **only** `DispatchRequest` from the concierge address. **No public ACP.** It re-verifies the token and content hash itself (defence in depth). The payment check is a stub until Phase 6.
2. `agents/dispatcher/mailer.py`: `smtplib` SMTP_SSL/STARTTLS run in `loop.run_in_executor`. Tenacity 3× backoff. On final failure the state is `SEND_FAILED` and a clear error goes back to chat; the request can be retried with `RETRY <company>`.
3. Send modes:
   - `dry_run` (default in tests): log the full email, mark it SENT, send nothing.
   - `demo_redirect` (default for the demo): every recipient becomes `DEMO_RECIPIENT_OVERRIDE`, and the body starts with `[DEMO: intended recipient X]`. **Assert that no real company address is used.**
   - `live`: requires `CONFIRM_LIVE=true` **and** in-chat approval.
4. Headers: `Reply-To: <local>+<request_id>@<domain>` from `REPLY_BASE`, CC to the user's email, `Message-ID` stored.
5. Write `requests` rows (`state=SENT`, `sent_at`, `deadline_at = sent_at + RESPONSE_DEADLINE_DAYS` via the clock) → `DispatchResult` → the concierge reports to the user → sends `TrackRequest` to the tracker.
6. Profile README with badges, stating that it is internal-only.

### Tests
- The SMTP helper in dry_run. demo_redirect rewrites every recipient. live without `CONFIRM_LIVE` is refused. SMTP failure → 3 retries → SEND_FAILED.

### Exit Gate
- `demo_redirect` email arrives in the demo inbox with the correct Reply-To plus-address and the DEMO header.

### Prompt for Antigravity
> Execute PHASE 5. Build the dispatcher (DispatchRequest only, no public ACP, re-verify token+hash), mailer with dry_run/demo_redirect/live modes, plus-addressed Reply-To, CC user, retry→SEND_FAILED, DB rows and TrackRequest handoff. Add tests. Verify one real demo_redirect email using the preflight SMTP settings. Commit.

---

## PHASE 6: Payment Protocol

**Goal:** monetization that the judges can see in the demo. (Can run in parallel with Phase 7.)

### Tasks
1. Read the Payment Protocol docs and examples (from `docs/api_notes.md`). Use **testnet / test tokens only**.
2. `shared/payments.py`: request/confirm/fail helpers, records written to the `payments` table (`payer`, `payee`, `amount`, `purpose`, `ref`, `status`, `ts`).
3. **User → concierge:** after APPROVE, the concierge sends a payment request for `batch_fee`. Dispatch happens only after confirmation. The `payment_ref` goes into every `DispatchRequest`, and the dispatcher checks it.
4. **Agent → agent:** the concierge pays discovery `discovery_lookup_fee` per lookup and pays the tracker `tracking_fee` per tracked request. The receiving agents check payment before doing paid work (with a bypass flag for local tests).
5. `PAYMENTS_BYPASS_FOR_DEMO=true`: logged and clearly labelled "demo mode: payment bypassed" in chat.
6. Monetization section for the README: per-batch fee, per-lookup and per-track inter-agent fees, and a future subscription for continuous monitoring.

### Tests
- No payment → no dispatch. Payment failure → clear message, the batch stays approved and can be retried. Bypass → dispatch with a label.

### Exit Gate
- A payment event is visible in the logs and the DB. The STATUS output (Phase 8) can read it.

### Prompt for Antigravity
> Execute PHASE 6. Implement the Fetch.ai Payment Protocol per current docs/examples (testnet only): user→concierge batch fee gating dispatch, concierge→discovery per-lookup and concierge→tracker per-track micro-payments, DB records, demo bypass flag with visible labelling, and payment gate tests. Document the monetization model. Commit.

---

## PHASE 7: Tracker, Mock Company, Demo Clock, Escalation

**Goal:** the long-running "keeps working after the hackathon" agent, compressed into about one minute for the demo.

### Tasks
1. `agents/tracker/state_machine.py`: states `SENT, ACKNOWLEDGED, RESOLVED, PARTIAL, REFUSED, NEEDS_INFO, OVERDUE, FOLLOWUP_SENT, ESCALATION_DRAFTED, SEND_FAILED`. Transitions follow the Master Prompt. **An auto-acknowledgement does not stop the deadline timer.** Only RESOLVED, PARTIAL or REFUSED stop it. Every transition is written to `events`.
2. `on_event("startup")`: rehydrate the open requests from the DB. `on_interval(period=…)`: sweep deadlines using `shared/clock.py`.
3. `agents/tracker/classifier.py`: ASI1 → `ReplyClassification {label, ticket_id?, retained_items[], legal_basis?, retention_period?, needs_info_detail?}`. Plus a plain-language explanation of any retention reasons.
4. Inputs: `InboundReply` from mock_company, a reply pasted into the concierge chat ("Reply from Swiggy: …"), and IMAP (Phase 8).
5. OVERDUE → draft a follow-up → back through the **same approval gate** (via the concierge) → FOLLOWUP_SENT → wait one more deadline cycle → **escalation draft**: timeline, copies of the correspondence, relief sought, a note that grievance redressal has been exhausted (s.13(3)), and the disclaimer. **Never auto-file. Never state a Board fee.**
6. NEEDS_INFO (for example the company asks for ID) → tell the user to reply to the company themselves. Never send ID documents.
7. RESOLVED → suggest a verification step (try logging in or resetting the password). Record the written confirmation and **never claim proof of deletion**.
8. Proactive `StatusUpdate` → concierge → user chat message on every state change.
9. `agents/mock_company/agent.py` (clearly labelled SIMULATED): scripted behaviour per company. Swiggy: auto-ack, then RESOLVED. Zomato: PARTIAL (keeps transaction records under tax law). Paytm: no reply, leading to OVERDUE → follow-up → escalation. Driven by the demo clock.
10. `shared/clock.py` demo mode: `DEMO_CLOCK_SPEED=86400` (1 real second = 1 day). `scripts/demo.sh` sets `SEND_MODE=demo_redirect`, `DEMO_CLOCK_SPEED`, `PAYMENTS_BYPASS_FOR_DEMO` (optional), and `DEBUG_MODE=true`.
11. Tracker ACP ("status of my requests") and a profile README with badges.

### Tests
- State machine, including "auto-ack does not stop the timer". Deadline logic with the fake clock. The classifier on **8 reply fixtures** (ack, resolved, partial-tax, partial-KYC, refused, needs-info-ID, irrelevant/spam, ack-with-ticket). The escalation draft contains no fee and includes the disclaimer.

### Exit Gate
- `scripts/demo.sh` runs the full Swiggy/Zomato/Paytm scenario end to end in under about 90 seconds through `client_agent.py`.

### Prompt for Antigravity
> Execute PHASE 7. Build the tracker (state machine with event log, on_event rehydration, on_interval deadline sweep via shared/clock.py, ASI1 reply classifier, follow-up and escalation drafts routed through the approval gate, proactive StatusUpdates, ACP), mock_company with the scripted Swiggy/Zomato/Paytm behaviours, DEMO_CLOCK and scripts/demo.sh. Add the state machine, deadline and 8-fixture classifier tests. Commit when demo.sh completes the scenario.

---

## PHASE 8: STATUS, DEBUG, Status/Reply Cards, IMAP Poller

**Goal:** a polished demo UX and visible evidence of the multi-agent run.

### Tasks
1. `STATUS`: a per-request table (company, state, deadline, ticket ID, verified flag, payments) as a **status card** with a text fallback.
2. **Reply-received card**: classification, extracted ticket or retained items, plain-language explanation, suggested next action plus the command buttons.
3. `DEBUG` (only when `DEBUG_MODE=true`): a compact trace of the last run. Agents called (names + short addresses), durations, ASI1 calls (purpose, latency, retries), payment events, the registry path (search vs env fallback), and MCP tool calls.
4. Optional `agents/tracker/imap_poller.py` (enabled by `IMAP_ENABLED`): poll the inbox, map `+<request_id>` to a request, and emit an `InboundReply`.
5. Command footer at the end of every major step. Disclaimer once per session.

### Exit Gate
- In ASI:One, `STATUS` and `DEBUG` both render correctly after a demo run.

### Prompt for Antigravity
> Execute PHASE 8. Add the STATUS command and status card, reply-received card, DEBUG trace (agents, addresses, durations, ASI1 calls, MCP calls, payments, registry path), optional IMAP poller with plus-address mapping, and consistent command footers. Commit.

---

## PHASE 9: Hardening and the Full Test Suite

**Goal:** every required test passes, and every failure path recovers gracefully (this earns the extra reliability credit).

### Required tests (checklist)
- [ ] Unit: intent extraction on 10 prompts
- [ ] Unit: state machine, including auto-ack does not stop the timer
- [ ] Unit: deadline logic with the fake clock
- [ ] Unit: reply classifier on 8 fixtures
- [ ] Unit: approval token (unapproved or tampered batch never sent)
- [ ] Unit: payment gate (no payment means no dispatch, unless bypassed)
- [ ] Unit: SMTP helper in dry_run
- [ ] Unit: discovery extractor on saved policy pages (verified vs unverified)
- [ ] Integration: `tests/client_agent.py` full flow (ACP, acks, gate, dispatch, tracking) without ASI:One
- [ ] Failure: discovery timeout
- [ ] Failure: Agentverse search failure leads to env fallback
- [ ] Failure: SMTP failure leads to SEND_FAILED and retry
- [ ] Failure: ASI1 error or rate limit leads to a retry and then a graceful message
- [ ] Failure: malformed prompt
- [ ] Failure: user never approves, so the session expires
- [ ] Failure: payment failure

### Also
- Run a security pass: no secrets in the repo, the HMAC secret is required at startup, the dispatcher sender allowlist is in place, and the PII guard is enforced in the drafter.
- `make test` runs fully offline (FakeASI1, fixtures, dry_run).

### Prompt for Antigravity
> Execute PHASE 9. Complete every test in the checklist, fix any failures, add the failure-path tests, ensure `make test` runs fully offline, and do a secrets/PII pass. Commit when 100% green.

---

## PHASE 10: Documentation, Demo and Submission

### Tasks
1. **README.md**: problem, target users, outcome, Mermaid architecture diagram, agent table (name, role, Agentverse address, profile URL), setup, `.env` guide, run and test commands, demo script, both badges, monetization model, "Simulated components" section, legal disclaimer, and the **Fetch.ai Technology Evidence** table:

   | Judging criterion | Fetch.ai tech | Code location | How to see it in the demo |
   |---|---|---|---|
   | Agentverse registration | 6 agents with profiles | `agents/*/README.md` | Agentverse profile URLs |
   | ACP | Chat protocol on concierge, discovery, drafter, tracker | `shared/acp.py` | ASI:One chat |
   | ASI1 reasoning | Intent, planning tool calls, extraction, drafting, classification | `shared/asi1_client.py` | `DEBUG` trace |
   | Multi-agent orchestration | Typed fan-out/fan-in | `agents/concierge/orchestrator.py` | `DEBUG` trace |
   | Dynamic discovery | Agentverse search with env fallback | `agents/concierge/registry.py` | `DEBUG` "registry path" |
   | Interactive Cards | Confirmation, review, status, reply cards | `agents/concierge/cards.py` | Review card |
   | Payment Protocol | User fee + agent-to-agent fees | `shared/payments.py` | STATUS card payments |
   | MCP | `find_grievance_contact`, `draft_erasure_request` | `mcp/server.py` | `DEBUG` MCP calls |
   | Long-running agent | on_interval / on_event tracker | `agents/tracker/` | Paytm escalation |

2. `docs/architecture.md`, `docs/deployment.md`, `docs/demo_script.md` (a timed 3–5 min script), `docs/legal_notes.md` (Act and Rules citations with dpdpa.com links, the enforcement timeline, the unverified deadline TODO, and the "not legal advice" disclaimer).
3. Every agent README has its address filled in and both badges.
4. Run the final `make test` and do a full ASI:One run-through using `scripts/demo.sh`.

### Manual checklist (the human does these; Antigravity cannot)
- [ ] Start every agent and confirm all are registered and online on Agentverse. Paste the addresses and profile URLs into the README
- [ ] Run the full scenario in **one** ASI:One conversation and create the **public shared chat URL**
- [ ] Record the **3–5 minute demo video** (show the review card, APPROVE, payment, the demo inbox, reply classification, the Paytm escalation, STATUS and DEBUG)
- [ ] Make the GitHub repo public. Check that `.env` is not committed
- [ ] Submit on the hackathon portal before **16:30 IST, 24 Oct 2026**: shared chat URL, Agentverse profile URLs, repo URL, video, short description

### Prompt for Antigravity
> Execute PHASE 10. Write the README (with Mermaid diagram, agent table, badges, monetization, simulated-parts section and the Fetch.ai Technology Evidence table), all docs/*, the timed demo script, and fill every agent README. Run the full test suite. Output the final manual checklist of what remains for the human.

---

## 4. Definition of Done (final acceptance)

In **one** ASI:One chat, a user types "Delete me from Swiggy, Zomato and Paytm", supplies a name and email, reviews the drafts on a card (with VERIFIED/UNVERIFIED badges), approves, pays (or uses the labelled demo bypass), sees the emails arrive in the demo inbox, watches the replies get classified (Swiggy resolved, Zomato partial with tax retention explained), watches Paytm go overdue, get a follow-up and then an escalation draft under the demo clock, and can run `STATUS` and `DEBUG`. `make test` is fully green. The README contains the Fetch.ai Technology Evidence table, all agent addresses and the badges.
