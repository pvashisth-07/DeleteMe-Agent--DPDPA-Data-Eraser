# DeleteMe Discovery Specialist Agent

![tag:innovationlab](https://img.shields.io/badge/innovationlab-3D8BD3)
![tag:hackathon](https://img.shields.io/badge/hackathon-5F43F1)

**Agent Address:** `agent1qtsk8vqfdywqg89mswxg29dpeftnnxq6jvmp0yphv9z5vcl67fgrjdsdnqg`

## Overview
The **DeleteMe Discovery Agent** is an autonomous specialist agent dedicated to locating verified Grievance Officer and Data Protection Officer (DPO) contact information for Indian companies and consumer platforms pursuant to **Rule 9 of the DPDP Rules 2025**.

## Capabilities
- Resolves app aliases (e.g., "Swiggy Instamart" -> "Bundl Technologies").
- Fetches and parses live privacy policy pages using BeautifulSoup and SQLite caching.
- Dynamically extracts Grievance Officers and validates email verification flags (`verified=true` strictly when present in the policy HTML).
- Exposes Model Context Protocol (MCP) tool integration.
- Operates standalone via ACP or as a specialist orchestrated by the Concierge agent.

## Example Prompts
- *"Find the grievance officer for Swiggy"*
- *"Grievance contact for Zomato"*
- *"Who is the DPO for Paytm?"*
