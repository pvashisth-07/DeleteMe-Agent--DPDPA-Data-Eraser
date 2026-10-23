#!/usr/bin/env bash
# Starts all DeleteMe agents with .env loaded and logs redirected to logs/

set -e

mkdir -p logs

echo "Starting DeleteMe Agents..."

if [ -f .venv/bin/python ]; then
    PYTHON=.venv/bin/python
else
    PYTHON=python
fi

$PYTHON -m agents.concierge.agent > logs/concierge.log 2>&1 &
echo "[+] Concierge Agent started (PID: $!) -> logs/concierge.log"

echo "All agents running in background. Use 'pkill -f agents.' to stop."
