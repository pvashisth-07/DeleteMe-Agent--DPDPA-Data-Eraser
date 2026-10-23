# DeleteMe Autonomous Tracker Agent

![tag:innovationlab](https://img.shields.io/badge/innovationlab-3D8BD3)
![tag:hackathon](https://img.shields.io/badge/hackathon-5F43F1)

**Agent Address:** `agent1qfs4f9apm6hg066577z8t2my673s9d0gcx2jjafeatujvpcpgr2ag9swpsd`

## Overview
The **DeleteMe Tracker Agent** is the long-running, autonomous monitoring and compliance agent in the DeleteMe multi-agent system. It watches over all dispatched personal data erasure notices, monitors compliance with statutory 30-day response deadlines under the **Digital Personal Data Protection Act, 2023 (DPDPA)**, classifies inbound company responses using ASI1 and heuristic models, generates statutory follow-up notices upon overdue status, and prepares formal grievance escalation complaints for the Data Protection Board of India under Section 13(3).

## Capabilities
- **Autonomous State Machine**: Enforces 10 distinct compliance states (`SENT`, `ACKNOWLEDGED`, `RESOLVED`, `PARTIAL`, `REFUSED`, `NEEDS_INFO`, `OVERDUE`, `FOLLOWUP_SENT`, `ESCALATION_DRAFTED`, `SEND_FAILED`).
- **Core Invariant**: Formal acknowledgment (`ACKNOWLEDGED`) does **not** stop the 30-day statutory response timer. Only terminal states (`RESOLVED`, `PARTIAL`, `REFUSED`) stop the deadline clock.
- **ASI1 Reply Classifier**: Extracts ticket IDs, retained records, statutory exceptions (Income Tax Act 1961, PMLA, RBI KYC guidelines), and generates plain-language explanations for citizens.
- **Statutory Deadline Sweep**: Runs periodic sweeps (`on_interval`) against real or simulated demo clocks (`DemoClock`), automatically flagging overdue requests.
- **Section 13(3) Grievance Escalation**: Drafts comprehensive complaint files for the Data Protection Board when grievance redressal is exhausted. **Never auto-files, never charges or states a Board fee**, and preserves complete evidentiary timelines.
- **Agent Chat Protocol (ACP)**: Responds to direct status queries from users inside ASI:One.

## Architecture Role
The Tracker is designed to keep running indefinitely after submission, continuously auditing company compliance on behalf of consumers.
