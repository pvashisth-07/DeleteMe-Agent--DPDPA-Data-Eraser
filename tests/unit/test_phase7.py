from datetime import datetime, timedelta
from pathlib import Path
import pytest

from agents.tracker.classifier import classify_reply, classify_reply_heuristic
from agents.tracker.escalation import generate_escalation_draft, generate_followup_draft
from agents.tracker.state_machine import (
    TERMINAL_STATES,
    TrackerState,
    can_transition,
    is_deadline_active,
    transition_request,
)
from shared.clock import DemoClock, get_clock
from shared.db import SqliteRepo


@pytest.fixture
def test_repo(tmp_path):
    db_file = tmp_path / "test_tracker.db"
    return SqliteRepo(str(db_file))


# ==============================================================================
# 1. State Machine & Transition Rules Tests
# ==============================================================================

def test_state_machine_valid_transitions(test_repo):
    req_id = "req_test_001"
    test_repo.save_request(
        request_id=req_id,
        batch_id="batch_001",
        session_id="sess_001",
        company_name="TestCorp",
        recipient_email="grievance@testcorp.com",
        user_email="user@example.com",
        subject="DPDPA Erasure",
        body="Delete my data",
        state="SENT",
        sent_at="2026-10-23T10:00:00",
        deadline_at="2026-11-22T10:00:00",
    )

    # SENT -> ACKNOWLEDGED
    ok, msg = transition_request(test_repo, req_id, "ACKNOWLEDGED", reason="Got auto-ack", ticket_id="TKT-123")
    assert ok is True
    req = test_repo.get_request(req_id)
    assert req["state"] == "ACKNOWLEDGED"
    assert req["ticket_id"] == "TKT-123"

    # ACKNOWLEDGED -> RESOLVED
    ok, msg = transition_request(test_repo, req_id, "RESOLVED", reason="Full purge confirmed")
    assert ok is True
    req = test_repo.get_request(req_id)
    assert req["state"] == "RESOLVED"

    # RESOLVED is terminal -> cannot transition back to SENT
    ok, msg = transition_request(test_repo, req_id, "SENT", reason="Illegal rewind")
    assert ok is False


def test_auto_ack_does_not_stop_deadline_timer():
    """
    CRITICAL INVARIANT:
    Auto-acknowledgement does NOT stop the statutory 30-day response deadline.
    Only terminal states (RESOLVED, PARTIAL, REFUSED) stop the timer.
    """
    assert is_deadline_active("SENT") is True
    assert is_deadline_active("ACKNOWLEDGED") is True
    assert is_deadline_active("NEEDS_INFO") is True
    assert is_deadline_active("FOLLOWUP_SENT") is True

    # Terminal states
    assert is_deadline_active("RESOLVED") is False
    assert is_deadline_active("PARTIAL") is False
    assert is_deadline_active("REFUSED") is False
    assert is_deadline_active("ESCALATION_DRAFTED") is False


# ==============================================================================
# 2. Classifier on 8 Reply Fixtures Tests
# ==============================================================================

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures" / "replies"


def test_classifier_fixture_ack():
    text = (FIXTURES_DIR / "ack.txt").read_text(encoding="utf-8")
    res = classify_reply_heuristic(body=text, subject="Swiggy Support")
    assert res.label == "ACKNOWLEDGED"


def test_classifier_fixture_resolved():
    text = (FIXTURES_DIR / "resolved.txt").read_text(encoding="utf-8")
    res = classify_reply_heuristic(body=text, subject="Confirmation of Erasure")
    assert res.label == "RESOLVED"
    assert "deleted" in res.plain_explanation.lower() or "purged" in res.plain_explanation.lower()


def test_classifier_fixture_partial_tax():
    text = (FIXTURES_DIR / "partial_tax.txt").read_text(encoding="utf-8")
    res = classify_reply_heuristic(body=text, subject="Zomato Legal")
    assert res.label == "PARTIAL"
    assert len(res.retained_items) > 0
    assert "income tax" in res.legal_basis.lower() or "cgst" in res.legal_basis.lower()
    assert "7 years" in (res.retention_period or "")


def test_classifier_fixture_partial_kyc():
    text = (FIXTURES_DIR / "partial_kyc.txt").read_text(encoding="utf-8")
    res = classify_reply_heuristic(body=text, subject="FinTech Privacy")
    assert res.label == "PARTIAL"
    assert len(res.retained_items) > 0
    assert "kyc" in res.legal_basis.lower() or "pmla" in res.legal_basis.lower()
    assert "5 years" in (res.retention_period or "")


def test_classifier_fixture_refused():
    text = (FIXTURES_DIR / "refused.txt").read_text(encoding="utf-8")
    res = classify_reply_heuristic(body=text, subject="Grievance Redressal")
    assert res.label == "REFUSED"
    assert "refused" in res.plain_explanation.lower() or "active legal claim" in res.plain_explanation.lower()


def test_classifier_fixture_needs_info_id():
    text = (FIXTURES_DIR / "needs_info_id.txt").read_text(encoding="utf-8")
    res = classify_reply_heuristic(body=text, subject="ID Verification Required")
    assert res.label == "NEEDS_INFO"
    assert res.needs_info_detail is not None
    assert "identity" in res.plain_explanation.lower()


def test_classifier_fixture_irrelevant_spam():
    text = (FIXTURES_DIR / "irrelevant_spam.txt").read_text(encoding="utf-8")
    res = classify_reply_heuristic(body=text, subject="Weekend Cravings")
    assert res.label == "IRRELEVANT"


def test_classifier_fixture_ack_with_ticket():
    text = (FIXTURES_DIR / "ack_with_ticket.txt").read_text(encoding="utf-8")
    res = classify_reply_heuristic(body=text, subject="Swiggy Helpdesk")
    assert res.label == "ACKNOWLEDGED"
    assert res.ticket_id == "SWIGGY-DPDP-8821"


# ==============================================================================
# 3. Deadline Logic with Fake Clock & Escalation Tests
# ==============================================================================

def test_deadline_and_escalation_lifecycle(test_repo):
    clock = get_clock()
    clock.reset(speed=1.0)
    start_sim = clock.now()

    req_id = "req_paytm_001"
    sent_at_iso = start_sim.isoformat()
    deadline_iso = (start_sim + timedelta(days=30)).isoformat()

    test_repo.save_request(
        request_id=req_id,
        batch_id="batch_paytm",
        session_id="sess_paytm",
        company_name="Paytm",
        recipient_email="grievance@paytm.com",
        user_email="citizen@india.in",
        subject="Erasure Request",
        body="Please erase all data",
        state="SENT",
        sent_at=sent_at_iso,
        deadline_at=deadline_iso,
    )

    # 1. Advance clock by 10 days -> Still active and within window
    clock.advance_days(10)
    req = test_repo.get_request(req_id)
    deadline_dt = datetime.fromisoformat(req["deadline_at"])
    assert clock.now() < deadline_dt

    # 2. Advance clock past 30 days (total 35 days) -> Overdue!
    clock.advance_days(25)
    assert clock.now() > deadline_dt

    # Transition to OVERDUE
    ok, msg = transition_request(
        test_repo,
        req_id,
        "OVERDUE",
        reason="Statutory response deadline elapsed",
        ticket_id="PAYTM-9988",
    )
    assert ok is True
    req = test_repo.get_request(req_id)
    assert req["state"] == "OVERDUE"

    # Generate follow-up notice
    followup = generate_followup_draft(
        company_name="Paytm",
        user_name="Aarav Sharma",
        ticket_id="PAYTM-9988",
        original_date=sent_at_iso[:10],
    )
    assert "FOLLOW-UP" in followup.subject
    assert "30" in followup.body
    assert "Paytm" in followup.body

    # Transition to FOLLOWUP_SENT
    ok, msg = transition_request(
        test_repo,
        req_id,
        "FOLLOWUP_SENT",
        reason="Follow-up dispatched after 30 days elapsed",
        ticket_id="PAYTM-9988",
    )
    assert ok is True
    req = test_repo.get_request(req_id)
    assert req["state"] == "FOLLOWUP_SENT"

    # 3. Advance clock another 35 days (total 70 days) -> Grievance exhausted!
    clock.advance_days(35)
    escalation = generate_escalation_draft(
        company_name="Paytm",
        user_name="Aarav Sharma",
        user_email="citizen@india.in",
        fiduciary_contact="grievance@paytm.com",
        sent_at=sent_at_iso,
        followup_at=deadline_iso,
        days_elapsed=70,
        ticket_id="PAYTM-9988",
    )

    # CRITICAL INVARIANTS CHECK:
    # 1. Never state a Board fee
    assert "fee" not in escalation.body.lower()
    # 2. Must contain statutory disclaimer
    assert "not legal advice" in escalation.body.lower()
    # 3. Must cite Section 13(3)
    assert "Section 13(3)" in escalation.body
    # 4. Must specify relief sought
    assert len(escalation.relief_sought) >= 3

    # Transition to ESCALATION_DRAFTED
    transition_request(
        test_repo,
        req_id,
        "ESCALATION_DRAFTED",
        reason="Grievance redressal exhausted under Section 13(3)",
        ticket_id="PAYTM-9988",
        payload={"escalation": escalation.model_dump()},
    )
    req = test_repo.get_request(req_id)
    assert req["state"] == "ESCALATION_DRAFTED"
    assert is_deadline_active(req["state"]) is False
