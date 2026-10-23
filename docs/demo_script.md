# DeleteMe Agent: Timed 3–5 Minute Demo Video Script

**Target Duration:** 3 minutes 45 seconds  
**Track:** Personal AI / Decentralized Multi-Agent Systems (Fetch-a-thon 3.0)  
**Presenter:** Single speaker with screen recording (ASI:One UI + Terminal / Demo Mailbox)

---

### [0:00 - 0:45] Act 1: The Problem & The Solution
**Visual:** Slide 1 / Title screen showing *"DeleteMe: Autonomous DPDPA 2023 Rights Agent"*, transitioning to the **ASI:One chat interface**.
**Speaker Script:**
> "Millions of Indian consumers use dozens of mobile apps every day—Swiggy for food, Zomato, Paytm, quick-commerce, and fintechs. But when you uninstall an app, your personal data—phone number, past addresses, transaction history, and behavioural habits—remains in their databases forever.
>
> India's **Digital Personal Data Protection Act, 2023 (DPDPA)** grants every citizen the statutory Right to Erasure under Section 12. But finding the designated Grievance Officer under DPDP Rule 9, formatting legal notices, verifying cryptographic hashes, and tracking 30-day compliance deadlines across 30 different apps is an impossible administrative burden.
>
> Enter **DeleteMe**—an autonomous multi-agent privacy system built on **Fetch.ai uAgents** and discoverable directly inside **ASI:One**."

---

### [0:45 - 1:45] Act 2: Conversational ACP, Intent Parsing & Multi-Agent Fan-Out
**Visual:** ASI:One Chat window. Presenter types: `Delete me from Swiggy, Zomato and Paytm`.
**Speaker Script:**
> "Right inside ASI:One, I speak naturally in plain language: *'Delete me from Swiggy, Zomato and Paytm'*.
>
> Watch the instant response: the Concierge agent acknowledges immediately via the **Agent Chat Protocol (ACP)** and recognizes that under Section 12, companies require account verification. It asks for my full name and registered email.
>
> I reply: *'My name is Aarav Sharma, email is aarav@example.com'*.
>
> I confirm with **YES**. In the background, the Concierge performs dynamic fan-out across our specialist uAgents on Agentverse:
> 1. The **Discovery Agent** uses our **Model Context Protocol (MCP)** tool `find_grievance_contact` to discover designated Grievance Officers.
> 2. The **Drafter Agent** compiles custom legal notices under Section 12 and the DPDP Rules 2025.
>
> Look at the **Interactive Review Card**: Swiggy is verified, Zomato is verified, and Paytm is marked with an unverified badge. Notice our **Strict PII Guard**—the agent prohibits and strips any sensitive identifiers like Aadhaar, PAN numbers, or passwords."

---

### [1:45 - 2:30] Act 3: Cryptographic HMAC Gate & Payment Protocol
**Visual:** User replies: `APPROVE batch_ba7e03cf`.
**Speaker Script:**
> "Crucially, DeleteMe enforces a strict **human-in-the-loop cryptographic gate**. No email can ever leave our dispatcher without a valid HMAC-SHA256 signature calculated over the exact draft content. If I edit or remove a company, the token is instantly invalidated.
>
> When I reply `APPROVE`, our **Payment Protocol** triggers:
> - The user pays a small service fee in testnet FET.
> - The Concierge autonomously issues micro-payments to the Discovery and Tracker agents for their work.
>
> The Dispatcher agent verifies the HMAC signature and the payment ref before sending via our configured send mode. Each outgoing notice is plus-addressed with `requests+<request_id>@deleteme.local`, ensuring complete auditability and CC'ing the user."

---

### [2:30 - 3:15] Act 4: Autonomous Long-Running Tracker & Statutory Deadline Sweep
**Visual:** Split screen: Terminal showing `demo.py` with `DEMO_CLOCK_SPEED=86400` (1 second = 1 day), alongside the simulated company replies.
**Speaker Script:**
> "DeleteMe doesn't stop after sending. It features an autonomous, long-running **Tracker Agent** that sweeps deadlines:
>
> 1. **Swiggy** replies with a ticket acknowledgment. Notice: an auto-reply **never** stops our statutory 30-day deadline timer! Later, Swiggy sends full confirmation and moves to `RESOLVED`.
> 2. **Zomato** replies with a **Partial Retention** notice. Our ASI1 reply classifier extracts that Zomato deleted the profile, but lawfully retains GST invoices for 7 years under Section 44AA of the Income Tax Act, 1961, providing a plain-English explanation to the citizen.
> 3. **Paytm** is unresponsive. We advance our simulated demo clock by 31 days. The Tracker detects the overdue status and generates a formal follow-up notice!
> 4. After another 30 days of silence, grievance redressal is exhausted under Section 13(3). The Tracker automatically drafts a formal **Escalation Complaint** for the **Data Protection Board of India**. It includes a full chronological timeline, relief sought, no fake board fees, and the statutory legal disclaimer."

---

### [3:15 - 3:45] Act 5: Observability, Evidence & Conclusion
**Visual:** ASI:One chat: typing `STATUS` and `DEBUG`.
**Speaker Script:**
> "At any time in ASI:One, I can type `STATUS` to view our **Interactive Status Card** showing every company's state, verified badge, and payment confirmation.
>
> Typing `DEBUG` reveals the complete telemetry trace: multi-agent calls, MCP executions, ASI1 reasoning latencies, and micropayment transactions across the Fetch.ai network.
>
> DeleteMe is open-source, fully test-covered with 62 green tests, registered on Agentverse, and ready to empower 1.4 billion Indian citizens to reclaim their digital sovereignty.
>
> Thank you!"
