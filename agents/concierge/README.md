# DeleteMe Concierge Agent

![tag:innovationlab](https://img.shields.io/badge/innovationlab-3D8BD3)
![tag:hackathon](https://img.shields.io/badge/hackathon-5F43F1)

**Agent Address:** `agent1qfq66d3thuzjl620d06sqn88j0ey650up6ltwt46qhljraz2fe4g50yap2z`

## Overview
The **DeleteMe Concierge Agent** is the primary conversational interface for Indian consumers exercising their data privacy rights under the **Digital Personal Data Protection Act, 2023 (DPDPA)**. It interacts directly with users inside **ASI:One** via the Agent Chat Protocol (ACP), understands natural language requests in English and Hinglish, discovers designated Grievance Officers under DPDP Rules 2025, orchestrates specialized legal drafting agents, enforces human-in-the-loop review with cryptographic HMAC tokens, handles micropayments, and monitors requests throughout their statutory 30-day lifecycle.

## Capabilities
- **Natural Language Intent Extraction**: Parses plain language requests to identify apps, companies, and user identity credentials.
- **Agent Chat Protocol (ACP)**: Native compatibility with ASI:One and Agentverse, always acknowledging messages immediately and managing session lifecycles.
- **Dynamic Multi-Agent Orchestration**: Discovers and coordinates with specialist Discovery, Drafter, Dispatcher, and Tracker agents on Agentverse.
- **Interactive Review & Approval**: Human-in-the-loop gating with HMAC-SHA256 authorization tokens and interactive card fallbacks.
- **Audit & Telemetry**: Full in-memory trace collection accessible via `DEBUG` and queryable request state via `STATUS`.

## Example Prompts for ASI:One
- *"Delete me from Swiggy, Zomato and Paytm"*
- *"pls remove me frm swiggy n zomato"*
- *"Mera data delete kardo zomato se"*
- *"STATUS"*
- *"DEBUG"*
- *"CANCEL"*
- *"APPROVE"*

## Architecture Role
The Concierge acts as the user's personal AI agent and orchestrator. It holds no sensitive credentials (such as Aadhaar or passwords) and routes verified requests to specialists while safeguarding consumer rights.
