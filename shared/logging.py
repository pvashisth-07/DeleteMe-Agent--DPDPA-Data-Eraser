import json
import logging
import sys
import time
from typing import Any, Dict, List, Optional
from shared.clock import now_iso


class TraceCollector:
    """Collects structured telemetry across agents and tools for the DEBUG command."""

    def __init__(self):
        self._traces: List[Dict[str, Any]] = []

    def record_agent_call(
        self,
        agent_name: str,
        agent_addr: str,
        action: str,
        duration_ms: float,
        status: str = "OK",
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        self._traces.append({
            "type": "agent_call",
            "timestamp": now_iso(),
            "agent_name": agent_name,
            "agent_addr": agent_addr,
            "action": action,
            "duration_ms": round(duration_ms, 2),
            "status": status,
            "details": details or {},
        })

    def record_asi1_call(
        self,
        purpose: str,
        model: str,
        latency_ms: float,
        retries: int = 0,
        success: bool = True,
    ) -> None:
        self._traces.append({
            "type": "asi1_call",
            "timestamp": now_iso(),
            "purpose": purpose,
            "model": model,
            "latency_ms": round(latency_ms, 2),
            "retries": retries,
            "success": success,
        })

    def record_mcp_call(
        self,
        tool: str,
        duration_ms: float,
        status: str = "OK",
    ) -> None:
        self._traces.append({
            "type": "mcp_call",
            "timestamp": now_iso(),
            "tool": tool,
            "duration_ms": round(duration_ms, 2),
            "status": status,
        })

    def record_payment(
        self,
        payer: str,
        payee: str,
        amount: str,
        currency: str,
        purpose: str,
        ref: str,
        status: str,
    ) -> None:
        self._traces.append({
            "type": "payment",
            "timestamp": now_iso(),
            "payer": payer,
            "payee": payee,
            "amount": amount,
            "currency": currency,
            "purpose": purpose,
            "ref": ref,
            "status": status,
        })

    def record_registry_lookup(
        self,
        target_role: str,
        method: str,  # 'agentverse_search' | 'env_fallback'
        resolved_addr: Optional[str],
    ) -> None:
        self._traces.append({
            "type": "registry",
            "timestamp": now_iso(),
            "target_role": target_role,
            "method": method,
            "resolved_addr": resolved_addr,
        })

    def clear(self) -> None:
        self._traces.clear()

    def get_traces(self) -> List[Dict[str, Any]]:
        return list(self._traces)

    def format_debug_trace(self) -> str:
        if not self._traces:
            return "No activity traces recorded for this session yet."

        lines = ["=== DEBUG TRACE LOG ==="]
        for t in self._traces[-20:]:  # last 20 events
            event_type = t.get("type", "event")
            if event_type == "agent_call":
                lines.append(
                    f"• [AGENT] {t['agent_name']} ({t['agent_addr'][:12]}...) "
                    f"-> {t['action']} | {t['duration_ms']}ms [{t['status']}]"
                )
            elif event_type == "asi1_call":
                lines.append(
                    f"• [ASI1] {t['purpose']} ({t['model']}) | {t['latency_ms']}ms "
                    f"(retries: {t['retries']}) [success: {t['success']}]"
                )
            elif event_type == "mcp_call":
                lines.append(f"• [MCP] Tool: {t['tool']} | {t['duration_ms']}ms [{t['status']}]")
            elif event_type == "payment":
                lines.append(
                    f"• [PAYMENT] {t['payer']} -> {t['payee']}: {t['amount']} {t['currency']} "
                    f"({t['purpose']}) [{t['status']}] ref={t['ref']}"
                )
            elif event_type == "registry":
                lines.append(
                    f"• [REGISTRY] {t['target_role']} via {t['method']} -> {t['resolved_addr']}"
                )
            else:
                lines.append(f"• [{event_type.upper()}] {json.dumps(t)}")
        return "\n".join(lines)


# Global collector instance
global_trace_collector = TraceCollector()


def setup_logger(name: str = "deleteme") -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        logger.setLevel(logging.INFO)
        handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter(
            fmt="[%(asctime)s] [%(levelname)s] [%(name)s]: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    return logger
