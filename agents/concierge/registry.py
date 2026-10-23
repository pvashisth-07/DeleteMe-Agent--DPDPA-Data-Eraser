import os
from typing import Dict, List, Optional
import httpx

from shared.config import get_settings
from shared.logging import global_trace_collector, setup_logger

logger = setup_logger("registry")

_REGISTRY_CACHE: Dict[str, str] = {}


async def resolve_agent_address(
    role: str,  # 'discovery' | 'drafter' | 'dispatcher' | 'tracker' | 'mock_company'
    tags: Optional[List[str]] = None,
) -> str:
    """
    Dynamically resolves specialist agent address:
    1. Checks in-memory cache.
    2. Queries Agentverse Almanac API (if AGENTVERSE_API_KEY configured).
    3. Falls back gracefully to deterministic environment variable.
    """
    settings = get_settings()
    role_key = role.lower()

    if role_key in _REGISTRY_CACHE:
        return _REGISTRY_CACHE[role_key]

    env_map = {
        "discovery": settings.DISCOVERY_ADDR or "agent1qtsk8vqfdywqg89mswxg29dpeftnnxq6jvmp0yphv9z5vcl67fgrjdsdnqg",
        "drafter": settings.DRAFTER_ADDR or "agent1q0su27nruzqk75kpwdtese6k083lde3lzj2aw5yawfw00y9d9u6kcffus6l",
        "dispatcher": settings.DISPATCHER_ADDR or "agent1qwmqhv5ll2fswhhvfxtzywfsxew2a3ufln2tsj8vzkzdktd789tpw7cmmup",
        "tracker": settings.TRACKER_ADDR or "agent1qfs4f9apm6hg066577z8t2my673s9d0gcx2jjafeatujvpcpgr2ag9swpsd",
        "mock_company": settings.MOCK_COMPANY_ADDR or "agent1qwhk3gqawq5auzsddt44mt77wrr8078yvzexp9l35cq22vymfus3qex5je4",
    }

    # 1. Try Agentverse API search if API key is provided
    if settings.AGENTVERSE_API_KEY:
        try:
            url = f"https://agentverse.ai/v1/almanac/search?interaction_type={role_key}"
            headers = {"Authorization": f"Bearer {settings.AGENTVERSE_API_KEY}"}
            async with httpx.AsyncClient(timeout=4.0) as client:
                resp = await client.get(url, headers=headers)
                if resp.status_code == 200:
                    data = resp.json()
                    agents = data.get("agents", [])
                    if agents:
                        resolved = agents[0].get("address")
                        _REGISTRY_CACHE[role_key] = resolved
                        global_trace_collector.record_registry_lookup(
                            target_role=role_key,
                            method="agentverse_search",
                            resolved_addr=resolved,
                        )
                        logger.info(f"Registry dynamically discovered {role_key} on Agentverse: {resolved}")
                        return resolved
        except Exception as e:
            logger.warning(f"Agentverse search failed for {role_key}: {e}. Falling back to env configuration.")

    # 2. Fall back to environment variable
    resolved_addr = env_map.get(role_key, env_map["discovery"])
    _REGISTRY_CACHE[role_key] = resolved_addr
    global_trace_collector.record_registry_lookup(
        target_role=role_key,
        method="env_fallback",
        resolved_addr=resolved_addr,
    )
    logger.info(f"Registry resolved {role_key} via env fallback: {resolved_addr}")
    return resolved_addr
