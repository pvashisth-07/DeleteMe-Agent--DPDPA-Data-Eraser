import pytest
from agents.concierge.intent import extract_intent, parse_deterministic_command
from shared.asi1_client import FakeASI1
from shared.models import IntentExtraction


@pytest.mark.asyncio
async def test_intent_1_standard_deletion():
    prompt = "Delete me from Swiggy, Zomato and Paytm. My name is Aarav Sharma and email is aarav@example.com"
    extraction, err = await extract_intent(prompt, client=FakeASI1())
    assert err is None
    assert extraction.intent == "delete"
    assert set(extraction.companies) == {"Swiggy", "Zomato", "Paytm"}
    assert extraction.name == "Aarav Sharma"
    assert extraction.email == "aarav@example.com"


@pytest.mark.asyncio
async def test_intent_2_informal_abbreviated():
    prompt = "pls remove me frm swiggy n zomato"
    extraction, err = await extract_intent(prompt, client=FakeASI1())
    assert err is None
    assert extraction.intent == "delete"
    assert "Swiggy" in extraction.companies
    assert "Zomato" in extraction.companies


@pytest.mark.asyncio
async def test_intent_3_hinglish():
    prompt = "mera data delete kardo zomato se please"
    extraction, err = await extract_intent(prompt, client=FakeASI1())
    assert err is None
    assert extraction.intent == "delete"
    assert "Zomato" in extraction.companies


@pytest.mark.asyncio
async def test_intent_4_missing_email_only_name():
    prompt = "Erase my personal records from PhonePe. I am Rohan Verma"
    extraction, err = await extract_intent(prompt, client=FakeASI1())
    assert err is None
    assert extraction.intent == "delete"
    assert "PhonePe" in extraction.companies
    assert extraction.email is None
    assert extraction.name == "Rohan Verma"


@pytest.mark.asyncio
async def test_intent_5_duplicate_companies():
    prompt = "Delete me from Swiggy, Zomato, swiggy and Swiggy again"
    extraction, err = await extract_intent(prompt, client=FakeASI1())
    assert err is None
    assert extraction.intent == "delete"
    assert extraction.companies == ["Swiggy", "Zomato"]  # Deduplicated


@pytest.mark.asyncio
async def test_intent_6_deterministic_status():
    prompt = "STATUS"
    extraction, err = await extract_intent(prompt, client=FakeASI1())
    assert err is None
    assert extraction.intent == "status"


@pytest.mark.asyncio
async def test_intent_7_deterministic_approve():
    prompt = "APPROVE batch_9981"
    extraction, err = await extract_intent(prompt, client=FakeASI1())
    assert err is None
    assert extraction.intent == "approve"
    assert extraction.raw_parameters.get("batch_id") == "batch_9981"


@pytest.mark.asyncio
async def test_intent_8_deterministic_remove_company():
    prompt = "REMOVE Zomato"
    extraction, err = await extract_intent(prompt, client=FakeASI1())
    assert err is None
    assert extraction.intent == "remove"
    assert "Zomato" in extraction.companies


@pytest.mark.asyncio
async def test_intent_9_empty_and_whitespace():
    prompt = "    "
    extraction, err = await extract_intent(prompt, client=FakeASI1())
    assert err is None
    assert extraction.intent == "empty"


@pytest.mark.asyncio
async def test_intent_10_pasted_company_reply():
    prompt = "Reply from Swiggy: We received your request. Ticket #SWG-8871 opened."
    extraction, err = await extract_intent(prompt, client=FakeASI1())
    assert err is None
    assert extraction.intent == "reply_paste"
    assert "Swiggy" in extraction.companies
    assert "Ticket #SWG-8871" in extraction.raw_parameters.get("reply_body", "")


@pytest.mark.asyncio
async def test_intent_llm_failure_graceful_fallback():
    class FailingLLM:
        async def complete_json(self, *args, **kwargs):
            raise RuntimeError("API timeout 504")

    prompt = "Delete me from Cred"
    extraction, err = await extract_intent(prompt, client=FailingLLM())
    assert extraction.intent == "other"
    assert "trouble thinking" in err
