# DeleteMe Drafter Specialist Agent

![tag:innovationlab](https://img.shields.io/badge/innovationlab-3D8BD3)
![tag:hackathon](https://img.shields.io/badge/hackathon-5F43F1)

**Agent Address:** `agent1q0su27nruzqk75kpwdtese6k083lde3lzj2aw5yawfw00y9d9u6kcffus6l`

## Overview
The **DeleteMe Drafter Agent** is an autonomous legal engineering specialist responsible for compiling tailored, statutory personal data erasure notices pursuant to **Section 12 of the Digital Personal Data Protection Act, 2023 (DPDPA)** and the DPDP Rules 2025.

## Capabilities
- Generates legally compliant erasure notices using curated templates (`law.yaml`).
- Enforces statutory pre-commencement "good-faith" wording by default (`law_in_force=false`).
- Explicitly demands written justification, statutory basis, and retention period for any data retained under statutory exceptions.
- Demands official grievance tracking / ticket reference ID within the 30-day response window.
- Computes SHA-256 content hashes over drafts for cryptographic tamper-proofing.
- **Strict PII Guard:** Proactively detects and rejects prohibited identifiers including Aadhaar, PAN numbers, OTPs, or passwords.
- Exposes Model Context Protocol (MCP) tool integration.

## Example Prompts
- *"Draft a DPDPA erasure request for Zomato"*
- *"Draft Section 12 notice for Swiggy"*
