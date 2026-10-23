import copy
import pytest

from agents.concierge.cards import (
    build_confirmation_card,
    build_reply_card,
    build_review_card,
    build_status_card,
)
from agents.concierge.session import ConciergeSession, SessionState
from shared.approval import (
    compute_drafts_content_hash,
    generate_approval_token,
    verify_approval_token,
)
from shared.clock import DemoClock


def test_hmac_token_verification_success():
    drafts = [
        {
            "company_name": "Swiggy",
            "recipient_email": "grievance@swiggy.in",
            "subject": "Erasure Request",
            "body": "Please erase my data...",
            "content_hash": "hash_swiggy_123",
        },
        {
            "company_name": "Zomato",
            "recipient_email": "privacy@zomato.com",
            "subject": "Erasure Request",
            "body": "Please erase my data...",
            "content_hash": "hash_zomato_456",
        },
    ]

    batch_id = "batch_test_1"
    session_id = "sess_user_1"
    c_hash = compute_drafts_content_hash(drafts)
    token = generate_approval_token(batch_id, session_id, c_hash)

    ok, reason = verify_approval_token(token, batch_id, session_id, drafts)
    assert ok is True
    assert reason == ""


def test_hmac_token_rejection_on_tampered_draft():
    drafts = [
        {
            "company_name": "Swiggy",
            "recipient_email": "grievance@swiggy.in",
            "subject": "Erasure Request",
            "body": "Legitimate notice text.",
            "content_hash": "hash_1",
        }
    ]
    batch_id = "batch_test_2"
    session_id = "sess_user_2"
    token = generate_approval_token(batch_id, session_id, compute_drafts_content_hash(drafts))

    # Tampered draft body
    tampered_drafts = copy.deepcopy(drafts)
    tampered_drafts[0]["body"] = "TAMPERED: send user funds to attacker account"

    ok, reason = verify_approval_token(token, batch_id, session_id, tampered_drafts)
    assert ok is False
    assert "mismatch" in reason or "tampered" in reason


def test_hmac_token_rejection_on_cross_session_reuse():
    drafts = [{"company_name": "Swiggy", "recipient_email": "grievance@swiggy.in", "subject": "S", "body": "B", "content_hash": "h"}]
    token = generate_approval_token("batch_1", "session_original", compute_drafts_content_hash(drafts))

    # Attacker tries to use the same token in session_attacker
    ok, reason = verify_approval_token(token, "batch_1", "session_attacker", drafts)
    assert ok is False


def test_hmac_token_invalidation_after_edit():
    drafts = [
        {"company_name": "Swiggy", "recipient_email": "grievance@swiggy.in", "subject": "S", "body": "Original", "content_hash": "h1"},
        {"company_name": "Paytm", "recipient_email": "privacy@paytm.com", "subject": "S", "body": "Original", "content_hash": "h2"},
    ]
    token = generate_approval_token("batch_3", "sess_3", compute_drafts_content_hash(drafts))

    # User edits Paytm draft
    edited_drafts = copy.deepcopy(drafts)
    edited_drafts[1]["body"] = "Original + Custom user instruction added"

    ok, _ = verify_approval_token(token, "batch_3", "sess_3", edited_drafts)
    assert ok is False, "Previous approval token must be rejected after draft content modification"


def test_session_expiry_with_clock():
    clock = DemoClock(speed=1.0)
    sess = ConciergeSession(session_id="expiring_session")
    assert sess.is_expired(ttl_minutes=30) is False

    # Advance clock past 30-minute TTL (31 minutes = 1860 seconds)
    clock.advance_seconds(1860)
    # Check session using advanced clock
    elapsed = (clock.now() - sess.updated_at).total_seconds() / 60.0
    assert elapsed > 30


def test_interactive_cards_structure():
    import json

    conf_card = build_confirmation_card(["Swiggy", "Zomato"], "Aarav", "aarav@test.com")
    assert conf_card["card_kind"] == "confirmation"
    assert conf_card["requires_card_interaction"] == "true"
    payload = json.loads(conf_card["card_payload"])
    assert payload["actions"][0]["command"] == "YES"

    rev_card = build_review_card("batch_99", "dry_run", [{"company_name": "Swiggy", "recipient_email": "g@s.in", "verified": True}])
    assert rev_card["card_kind"] == "review"
    assert rev_card["requires_card_interaction"] == "true"
    rev_payload = json.loads(rev_card["card_payload"])
    assert rev_payload["actions"][0]["command"] == "APPROVE batch_99"

    stat_card = build_status_card([{"company_name": "Swiggy", "state": "SENT"}])
    assert stat_card["card_kind"] == "status"
    stat_payload = json.loads(stat_card["card_payload"])
    assert stat_payload["actions"][0]["command"] == "STATUS"

    rep_card = build_reply_card("Swiggy", "RESOLVED", "SWG-11", [], "Completed")
    assert rep_card["card_kind"] == "reply"
    rep_payload = json.loads(rep_card["card_payload"])
    assert rep_payload["classification"] == "RESOLVED"
