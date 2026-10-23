"""
DeleteMe DPDPA Agent - Agentverse & ASI:One Chat Agent Registration Script
Registers the Concierge agent into Agentverse and the ASI:One Chat network.
"""

import os
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shared.config import get_settings
from uagents_core.utils.registration import (
    register_chat_agent,
    RegistrationRequestCredentials,
)


def main():
    settings = get_settings()
    
    # Check for Agentverse API key
    agentverse_key = (
        os.environ.get("AGENTVERSE_KEY")
        or settings.AGENTVERSE_API_KEY
        or os.environ.get("AGENTVERSE_API_KEY")
    )

    if not agentverse_key or not agentverse_key.strip():
        print("=" * 70)
        print("ERROR: AGENTVERSE_KEY not found!")
        print("Please click the purple [Copy] button next to AGENTVERSE_KEY on the")
        print("Agentverse screen and paste it into .env under AGENTVERSE_KEY=...")
        print("=" * 70)
        sys.exit(1)

    seed_phrase = (
        os.environ.get("AGENT_SEED_PHRASE")
        or settings.CONCIERGE_SEED
    )

    print("=" * 70)
    print("   Registering DeleteMe Concierge as an ASI:One Chat Agent...")
    print("=" * 70)
    print(f"[*] Agent Name:     deleteme_concierge")
    print(f"[*] Seed Phrase:    {seed_phrase[:15]}... (deterministic)")
    print(f"[*] Endpoint:       https://agentverse.ai/v2/agents/mailbox/submit")

    try:
        success = register_chat_agent(
            name="deleteme_concierge",
            endpoint="https://agentverse.ai/v2/agents/mailbox/submit",
            active=True,
            credentials=RegistrationRequestCredentials(
                agentverse_api_key=agentverse_key.strip(),
                agent_seed_phrase=seed_phrase.strip(),
            ),
            description="DeleteMe Concierge: Privacy rights assistant enforcing personal data erasure under India DPDPA 2023.",
            readme=(
                "Enforce your data erasure rights under India's Digital Personal Data Protection Act (DPDPA 2023). "
                "Automatically discover grievance officers, draft Section 12 notices, and track 30-day statutory deadlines."
            ),
            starter_prompts=[
                "Delete me from Swiggy, Zomato and Paytm",
                "Check status of my erasure requests",
                "What are my rights under Section 12 DPDPA?",
            ],
        )

        if success:
            print("[+] Registration SUCCESSFUL! The agent is now registered on Agentverse.")
            print("[+] You can now click 'Evaluate my agent\'s registration' on Agentverse!")
        else:
            print("[!] register_chat_agent returned False. Please check your credentials.")
    except Exception as e:
        print(f"[!] Registration failed with exception: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
