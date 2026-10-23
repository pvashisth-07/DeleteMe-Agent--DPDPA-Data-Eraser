#!/bin/bash
# DeleteMe Agent: Full Scenario Demonstration
# Canonical Swiggy / Zomato / Paytm flow with Demo Clock

set -e
export SEND_MODE=demo_redirect
export DEMO_CLOCK_SPEED=86400
export PAYMENTS_BYPASS_FOR_DEMO=true
export DEBUG_MODE=true

echo "=========================================================="
echo " Starting DeleteMe Full Scenario Demo (DPDPA 2023 Agent)"
echo "=========================================================="

python scripts/demo.py
