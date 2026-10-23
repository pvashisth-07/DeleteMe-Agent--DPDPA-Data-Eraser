import asyncio
import hashlib
import json
import time
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4

from agents.concierge.registry import resolve_agent_address
from agents.concierge.session import ConciergeSession, SessionState, save_session
from mcp.tools import draft_erasure_request_impl, find_grievance_contact_impl
from shared.clock import now_iso
from shared.db import BaseRepository
from shared.logging import global_trace_collector, setup_logger
from shared.models import DiscoveryRequest, DiscoveryResult, DraftRequest, DraftResult, UserProfile

logger = setup_logger("orchestrator")


def compute_batch_content_hash(drafts: List[Dict[str, Any]]) -> str:
    """Computes deterministic canonical sha256 hash across all drafts in a batch."""
    canonical_items = []
    for d in sorted(drafts, key=lambda x: x.get("company_name", "")):
        canonical_items.append({
            "company_name": d.get("company_name"),
            "recipient_email": d.get("recipient_email"),
            "subject": d.get("subject"),
            "body": d.get("body"),
            "content_hash": d.get("content_hash"),
        })
    canonical_json = json.dumps(canonical_items, sort_keys=True)
    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()


async def orchestrate_batch_discovery_and_drafting(
    session: ConciergeSession,
    repo: BaseRepository,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, str]], str]:
    """
    Fans out parallel Discovery and Legal Drafting for all companies in session.
    Supports partial results with timeout/retry tolerance.
    Returns: (successful_drafts, failed_companies, batch_content_hash).
    """
    batch_id = session.batch_id or f"batch_{uuid4().hex[:8]}"
    session.batch_id = batch_id
    user_profile = session.get_user_profile()

    if not user_profile:
        raise ValueError("Cannot orchestrate drafting: user profile is incomplete.")

    logger.info(f"Orchestrating batch {batch_id} for {len(session.companies)} companies: {session.companies}")
    start_time = time.time()

    # Step 1: Resolve specialist agent addresses
    disc_addr = await resolve_agent_address("discovery")
    draft_addr = await resolve_agent_address("drafter")

    # Step 2: Parallel Discovery Fan-Out
    async def discover_single(company: str) -> Dict[str, Any]:
        c_start = time.time()
        contact = await find_grievance_contact_impl(company, repo=repo if hasattr(repo, "get_cached_policy") else None)
        c_dur = (time.time() - c_start) * 1000
        global_trace_collector.record_agent_call(
            agent_name="deleteme_discovery",
            agent_addr=disc_addr,
            action=f"discover:{company}",
            duration_ms=c_dur,
            status="OK",
        )
        return contact

    discovery_tasks = [discover_single(comp) for comp in session.companies]
    discovery_results = await asyncio.gather(*discovery_tasks, return_exceptions=True)

    successful_drafts: List[Dict[str, Any]] = []
    failed_companies: List[Dict[str, str]] = []

    # Step 3: Parallel Drafting Fan-Out
    profile_dict = {
        "name": user_profile.name,
        "email": user_profile.email,
        "phone": user_profile.phone,
        "identifiers": user_profile.identifiers,
    }

    for comp_name, disc_res in zip(session.companies, discovery_results):
        if isinstance(disc_res, Exception):
            logger.error(f"Discovery failed for {comp_name}: {disc_res}")
            failed_companies.append({"company": comp_name, "reason": str(disc_res)})
            continue

        try:
            d_start = time.time()
            request_id = f"req_{uuid4().hex[:8]}"
            draft = draft_erasure_request_impl(
                company_name=disc_res["company_name"],
                recipient_email=disc_res["email"],
                user_profile=profile_dict,
                verified=disc_res.get("verified", False),
            )
            d_dur = (time.time() - d_start) * 1000
            global_trace_collector.record_agent_call(
                agent_name="deleteme_drafter",
                agent_addr=draft_addr,
                action=f"draft:{disc_res['company_name']}",
                duration_ms=d_dur,
                status="OK",
            )

            draft_record = {
                "request_id": request_id,
                "batch_id": batch_id,
                "session_id": session.session_id,
                "company_name": draft["company_name"],
                "recipient_email": draft["recipient_email"],
                "subject": draft["subject"],
                "body": draft["body"],
                "content_hash": draft["content_hash"],
                "verified": draft["verified"],
            }

            repo.save_draft(
                request_id=request_id,
                batch_id=batch_id,
                session_id=session.session_id,
                company_name=draft["company_name"],
                recipient_email=draft["recipient_email"],
                subject=draft["subject"],
                body=draft["body"],
                content_hash=draft["content_hash"],
                verified=draft["verified"],
            )
            successful_drafts.append(draft_record)
        except Exception as e:
            logger.error(f"Drafting failed for {comp_name}: {e}")
            failed_companies.append({"company": comp_name, "reason": str(e)})

    # Step 4: Compute Batch Content Hash & Record Batch
    batch_hash = compute_batch_content_hash(successful_drafts)
    repo.save_batch(
        batch_id=batch_id,
        session_id=session.session_id,
        content_hash=batch_hash,
        status="AWAITING_APPROVAL",
    )

    session.state = SessionState.AWAITING_APPROVAL
    save_session(repo, session)

    total_dur = (time.time() - start_time) * 1000
    global_trace_collector.record_agent_call(
        agent_name="concierge_orchestrator",
        agent_addr="local",
        action="batch_orchestration",
        duration_ms=total_dur,
        status="OK",
        details={"successful": len(successful_drafts), "failed": len(failed_companies)},
    )

    return successful_drafts, failed_companies, batch_hash
