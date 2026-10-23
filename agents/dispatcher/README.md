# DeleteMe Dispatcher Agent (Internal)

![tag:innovationlab](https://img.shields.io/badge/innovationlab-3D8BD3)
![tag:hackathon](https://img.shields.io/badge/hackathon-5F43F1)

**Agent Address:** `agent1qwmqhv5ll2fswhhvfxtzywfsxew2a3ufln2tsj8vzkzdktd789tpw7cmmup`

## Overview
The **DeleteMe Dispatcher Agent** is an internal, non-public autonomous worker dedicated to the secure and verified outbound transmission of DPDPA erasure requests. It enforces rigorous defence-in-depth verification before any email is dispatched.

## Security Controls
- **Internal Only**: Does not expose public ACP chat protocols. Only accepts typed `DispatchRequest` models.
- **Cryptographic Gate**: Re-verifies HMAC-SHA256 authorization tokens and content hashes independently before firing any outbound socket connection.
- **Payment Verification Gate**: Re-verifies user fee payment completion or authorized demo bypass status.
- **Send Modes**:
  - `dry_run`: Purely local execution; logs and records state without network transmission.
  - `demo_redirect`: Rewrites all recipient addresses to `DEMO_RECIPIENT_OVERRIDE` with explicit simulation headers.
  - `live`: Hard-blocked unless `CONFIRM_LIVE=true` is explicitly provided.
- **Plus-Addressed Routing**: Injects uniquely tagged `Reply-To: requests+<request_id>@domain` headers for deterministic reply correlation.
