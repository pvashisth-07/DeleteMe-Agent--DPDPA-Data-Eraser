# Project Assumptions & Technical Decisions Log

This document records technical and architectural decisions, ambiguities resolved, and working assumptions per the project specification.

| Date | Decision / Ambiguity | Resolution | Rationale |
|---|---|---|---|
| 2026-10-23 | DPDPA Enforcement Timeline | Default `law_in_force: false`. All initial erasure notices use good-faith pre-commencement phrasing referencing DPDPA 2023 s.12 and DPDP Rules 2025 (Rights of Data Principals). | Under G.S.R. 843(E), rights under ss.11–17 commence 18 months post-publication. Framing requests as proactive good-faith compliance prevents legal misrepresentation while asserting rights. |
| 2026-10-23 | Response Deadline Days | Configured to 30 days default (`RESPONSE_DEADLINE_DAYS: 30`) with verification note for DPDP Rules 2025 PDF. | Neither dpdpa.com nor Act text specifies a fixed statutory days window for s.12 erasure. 30 days represents standard industry and regulatory reasonableness. |
| 2026-10-23 | Grievance Contact Verification | `verified=true` strictly when contact email is directly extracted from the live fetched privacy policy HTML. Otherwise fallback to `privacy@<domain>` with `verified=false`. | Prevents fabricated or inaccurate legal correspondence to companies. |
| 2026-10-23 | Data Protection Board Fee | No fee specified or included in any escalation draft. | Neither DPDPA 2023 s.13 nor s.18-26 specifies a Board grievance filing fee for data principals. |
| 2026-10-23 | ASI:One API Configuration | Base URL: `https://api.asi1.ai/v1`, Model: `asi1` (fallback: `asi1-mini`). | Standard OpenAI-compatible format confirmed from ASI:One developer quickstart. |
| 2026-10-23 | MCP Server Architecture | Using `mcp==2.3.0` with `from mcp.server.mcpserver import MCPServer`. | In MCP v2.x, `FastMCP` was migrated to `MCPServer` providing `@server.tool()` decorators and stdio/SSE runners. |
| 2026-10-23 | Agentverse Mailbox & Registration | Mailbox agents utilized for local development and live connection to Agentverse via `mailbox=True`. Manual registration and verification guide in `scripts/register_agents.md`. | Allows agents to run locally behind NAT while receiving messages through Agentverse. |
| 2026-10-23 | Payment Protocol | Standard `uagents_core.contrib.protocols.payment` models (`RequestPayment`, `CommitPayment`, `CompletePayment`) with `PAYMENTS_BYPASS_FOR_DEMO=true` supported for reliable live judging demos. | Guarantees deterministic demonstrations even if testnet faucets or network latency fluctuate during judging. |
| 2026-10-23 | Time Management | All time references routed strictly through `shared/clock.py` (`DemoClock`) to support accelerated demo timelines (`DEMO_CLOCK_SPEED=86400`). | Enables realistic 30-day escalation and follow-up scenarios to unfold in ~60-90 seconds during evaluation. |
