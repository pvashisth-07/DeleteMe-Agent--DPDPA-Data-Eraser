import json
from pathlib import Path
import pytest

from agents.concierge.orchestrator import compute_batch_content_hash, orchestrate_batch_discovery_and_drafting
from agents.concierge.registry import resolve_agent_address
from agents.concierge.session import ConciergeSession, SessionState
from mcp.tools import (
    compute_content_hash,
    draft_erasure_request_impl,
    extract_officer_and_email_from_html,
    find_grievance_contact_impl,
    validate_no_prohibited_pii,
)
from shared.db import CtxStorageRepo
from shared.logging import global_trace_collector
from shared.models import UserProfile

BASE_DIR = Path(__file__).resolve().parent.parent.parent


def test_discovery_on_verified_fixture():
    fixture_path = BASE_DIR / "tests" / "fixtures" / "policies" / "swiggy_policy.html"
    assert fixture_path.exists()
    html = fixture_path.read_text(encoding="utf-8")

    officer, email, verified = extract_officer_and_email_from_html(html, "swiggy.in")
    assert verified is True
    assert email == "grievance@swiggy.in"
    assert officer == "Mr. Arun Kumar"


def test_discovery_on_unverified_fixture():
    fixture_path = BASE_DIR / "tests" / "fixtures" / "policies" / "unverified_company.html"
    assert fixture_path.exists()
    html = fixture_path.read_text(encoding="utf-8")

    officer, email, verified = extract_officer_and_email_from_html(html, "unknownapp.com")
    assert verified is False
    assert email == "privacy@unknownapp.com"
    assert officer is None


def test_drafter_statutory_content_and_disclaimer():
    profile = {
        "name": "Pooja Hegde",
        "email": "pooja@example.com",
        "phone": "+919876543210",
        "identifiers": {"account_id": "acc_pooja_11"},
    }

    draft = draft_erasure_request_impl(
        company_name="Swiggy",
        recipient_email="grievance@swiggy.in",
        user_profile=profile,
        verified=True,
    )

    body = draft["body"]
    assert "Section 12" in body or "Section 12" in draft["subject"]
    assert "Pooja Hegde" in body
    assert "pooja@example.com" in body
    assert "+919876543210" in body
    assert "acc_pooja_11" in body
    assert "written list" in body
    assert "retention period" in body
    assert "Notice:" in body or "disclaimer" in body.lower()
    assert draft["content_hash"] == compute_content_hash(draft["subject"], body, "grievance@swiggy.in")


def test_pii_guard_blocks_aadhaar_and_pan():
    # Valid text
    validate_no_prohibited_pii("My name is Rohan and my email is rohan@example.com")

    # Prohibited Aadhaar (12 digits)
    with pytest.raises(ValueError, match="Aadhaar"):
        validate_no_prohibited_pii("My Aadhaar is 5544 3322 1100 please verify")

    # Prohibited PAN (5 letters, 4 numbers, 1 letter)
    with pytest.raises(ValueError, match="PAN"):
        validate_no_prohibited_pii("My PAN card number is ABCDE1234F")

    # Prohibited Password/OTP
    with pytest.raises(ValueError, match="credentials/OTP"):
        validate_no_prohibited_pii("My password: mysecretpassword123")


@pytest.mark.asyncio
async def test_registry_fallback_and_logging():
    global_trace_collector.clear()
    addr = await resolve_agent_address("discovery")
    assert addr.startswith("agent1")

    traces = [t for t in global_trace_collector.get_traces() if t.get("type") == "registry"]
    assert len(traces) >= 1
    assert traces[0]["target_role"] == "discovery"
    assert traces[0]["method"] in ("env_fallback", "agentverse_search")


@pytest.mark.asyncio
async def test_orchestrator_parallel_fanout_and_partial_results(monkeypatch):
    repo = CtxStorageRepo()
    session = ConciergeSession(
        session_id="test_sess_orchestrate",
        user_name="Dev User",
        user_email="dev@example.com",
        companies=["Swiggy", "Zomato", "FailingCompanyXYZ"],
    )

    # Mock find_grievance_contact_impl to fail specifically on FailingCompanyXYZ
    orig_find = find_grievance_contact_impl

    async def mock_find(company, repo=None):
        if company == "FailingCompanyXYZ":
            raise TimeoutError("Network timeout connecting to FailingCompanyXYZ")
        return await orig_find(company, repo=repo)

    monkeypatch.setattr("agents.concierge.orchestrator.find_grievance_contact_impl", mock_find)

    drafts, failures, batch_hash = await orchestrate_batch_discovery_and_drafting(session, repo)

    assert len(drafts) == 2
    assert {"Swiggy", "Zomato"} == {d["company_name"] for d in drafts}
    assert len(failures) == 1
    assert failures[0]["company"] == "FailingCompanyXYZ"
    assert "timeout" in failures[0]["reason"].lower()
    assert batch_hash is not None
    assert session.state == SessionState.AWAITING_APPROVAL
