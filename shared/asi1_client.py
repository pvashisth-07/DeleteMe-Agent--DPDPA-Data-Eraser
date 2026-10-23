import json
import logging
import re
import time
from typing import Any, Dict, List, Optional, Type, TypeVar
from openai import AsyncOpenAI
from pydantic import BaseModel, ValidationError
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from shared.logging import global_trace_collector, setup_logger
from shared.models import (
    ContactExtraction,
    EmailDraft,
    EscalationDraft,
    IntentExtraction,
    ReplyClassification,
)

logger = setup_logger("asi1_client")
T = TypeVar("T", bound=BaseModel)


class ASI1Client:
    def __init__(
        self,
        api_key: str = "mock-key",
        base_url: str = "https://api.asi1.ai/v1",
        model: str = "asi1",
    ):
        self.api_key = api_key
        self.base_url = base_url
        self.model = model
        self.client = AsyncOpenAI(api_key=api_key, base_url=base_url)

    @retry(
        reraise=True,
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
    )
    async def _raw_chat_completion(
        self,
        messages: List[Dict[str, str]],
        json_mode: bool = True,
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> Any:
        kwargs: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
        }
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        if tools:
            kwargs["tools"] = tools

        return await self.client.chat.completions.create(**kwargs)

    async def complete_json(
        self,
        schema: Type[T],
        messages: List[Dict[str, str]],
        purpose: str = "json_completion",
    ) -> T:
        schema_prompt = (
            f"\nYou must respond ONLY with a valid JSON object matching this schema:\n"
            f"{json.dumps(schema.model_json_schema())}"
        )
        augmented_messages = list(messages)
        if augmented_messages and augmented_messages[-1]["role"] == "user":
            augmented_messages[-1] = {
                "role": "user",
                "content": augmented_messages[-1]["content"] + "\n" + schema_prompt,
            }
        else:
            augmented_messages.append({"role": "system", "content": schema_prompt})

        start_time = time.time()
        retries = 0
        try:
            resp = await self._raw_chat_completion(augmented_messages, json_mode=True)
            content = resp.choices[0].message.content or "{}"
            parsed = schema.model_validate_json(content)
            latency = (time.time() - start_time) * 1000
            global_trace_collector.record_asi1_call(
                purpose=purpose,
                model=self.model,
                latency_ms=latency,
                retries=0,
                success=True,
            )
            return parsed
        except (ValidationError, json.JSONDecodeError) as e:
            logger.warning(f"ASI1 JSON validation failed for {purpose}: {e}. Attempting repair retry.")
            retries = 1
            repair_messages = list(augmented_messages)
            repair_messages.append({
                "role": "assistant",
                "content": content if "content" in locals() else "{}",
            })
            repair_messages.append({
                "role": "user",
                "content": f"The response was invalid JSON or did not conform to the schema: {e}. Fix the errors and return valid JSON only.",
            })

            repair_resp = await self._raw_chat_completion(repair_messages, json_mode=True)
            repair_content = repair_resp.choices[0].message.content or "{}"
            parsed = schema.model_validate_json(repair_content)
            latency = (time.time() - start_time) * 1000
            global_trace_collector.record_asi1_call(
                purpose=purpose,
                model=self.model,
                latency_ms=latency,
                retries=retries,
                success=True,
            )
            return parsed
        except Exception as e:
            latency = (time.time() - start_time) * 1000
            global_trace_collector.record_asi1_call(
                purpose=purpose,
                model=self.model,
                latency_ms=latency,
                retries=retries,
                success=False,
            )
            raise e

    async def tool_call(
        self,
        messages: List[Dict[str, str]],
        tools: List[Dict[str, Any]],
        purpose: str = "tool_call",
    ) -> Any:
        start_time = time.time()
        try:
            resp = await self._raw_chat_completion(messages, json_mode=False, tools=tools)
            latency = (time.time() - start_time) * 1000
            global_trace_collector.record_asi1_call(
                purpose=purpose,
                model=self.model,
                latency_ms=latency,
                retries=0,
                success=True,
            )
            return resp.choices[0].message
        except Exception as e:
            latency = (time.time() - start_time) * 1000
            global_trace_collector.record_asi1_call(
                purpose=purpose,
                model=self.model,
                latency_ms=latency,
                retries=0,
                success=False,
            )
            raise e


class FakeASI1:
    """Deterministic canned response generator for offline testing and fast verification."""

    def __init__(self, model: str = "fake-asi1"):
        self.model = model

    async def complete_json(
        self,
        schema: Type[T],
        messages: List[Dict[str, str]],
        purpose: str = "fake_json_completion",
    ) -> T:
        user_texts = [m.get("content", "") for m in messages if m.get("role") == "user"]
        prompt_text = " ".join(user_texts) if user_texts else " ".join([m.get("content", "") for m in messages])
        start_time = time.time()

        if schema == IntentExtraction:
            result = self._extract_intent(prompt_text)
        elif schema == ContactExtraction:
            result = self._extract_contact(prompt_text)
        elif schema == EmailDraft:
            result = self._draft_email(prompt_text)
        elif schema == ReplyClassification:
            result = self._classify_reply(prompt_text)
        elif schema == EscalationDraft:
            result = self._draft_escalation(prompt_text)
        else:
            result = {}

        latency = (time.time() - start_time) * 1000
        global_trace_collector.record_asi1_call(
            purpose=purpose,
            model=self.model,
            latency_ms=latency,
            retries=0,
            success=True,
        )
        return schema.model_validate(result)

    def _extract_intent(self, text: str) -> Dict[str, Any]:
        # Clean text
        text_norm = text.lower()

        # Intent detection
        intent = "other"
        if any(w in text_norm for w in ["delete", "remove", "erasure", "erase", "bhool jao", "delete kardo", "hatao"]):
            intent = "delete"
        elif any(w in text_norm for w in ["status", "kya hua", "progress", "track"]):
            intent = "status"
        elif "approve" in text_norm:
            intent = "approve"
        elif "cancel" in text_norm:
            intent = "cancel"
        elif "edit" in text_norm:
            intent = "edit"
        elif text_norm.startswith("reply from") or "inbound reply" in text_norm:
            intent = "reply_paste"
        elif "debug" in text_norm:
            intent = "debug"

        # Canonical Indian consumer apps mapping
        known_map = {
            "swiggy": "Swiggy",
            "zomato": "Zomato",
            "paytm": "Paytm",
            "phonepe": "PhonePe",
            "flipkart": "Flipkart",
            "myntra": "Myntra",
            "meesho": "Meesho",
            "ola": "Ola",
            "uber": "Uber India",
            "rapido": "Rapido",
            "zepto": "Zepto",
            "blinkit": "Blinkit",
            "bigbasket": "BigBasket",
            "nykaa": "Nykaa",
            "makemytrip": "MakeMyTrip",
            "goibibo": "Goibibo",
            "irctc": "IRCTC",
            "bookmyshow": "BookMyShow",
            "dream11": "Dream11",
            "cred": "CRED",
            "groww": "Groww",
            "zerodha": "Zerodha",
        }
        found_companies = []
        for k, canonical in known_map.items():
            if re.search(r"\b" + k + r"\b", text_norm):
                found_companies.append(canonical)

        # Email extraction
        email_match = re.search(r"[\w\.-]+@[\w\.-]+\.\w+", text)
        email = email_match.group(0) if email_match else None

        # Phone extraction
        phone_match = re.search(r"(\+91[\-\s]?)?[6-9]\d{9}", text)
        phone = phone_match.group(0) if phone_match else None

        # Name extraction heuristic
        name = None
        name_match = re.search(r"(?:my name is|i am|name[:=])\s*([a-zA-Z\s]+?)(?:,|\.|$|\band\b)", text, re.IGNORECASE)
        if name_match:
            name = name_match.group(1).strip().title()

        return {
            "intent": intent,
            "companies": list(dict.fromkeys(found_companies)),
            "name": name,
            "email": email,
            "phone": phone,
            "identifiers": {"phone": phone} if phone else {},
            "raw_parameters": {},
        }

    def _extract_contact(self, text: str) -> Dict[str, Any]:
        # Extract email from policy text
        email_match = re.search(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+", text)
        email = email_match.group(0) if email_match else None

        officer_match = re.search(r"(?:grievance officer|nodal officer|data protection officer)[:\s]+([a-zA-Z\s]+)", text, re.IGNORECASE)
        officer = officer_match.group(1).strip() if officer_match else None

        return {
            "officer_name": officer,
            "email": email,
            "address": "Bangalore, India",
            "found_rule9_contact": bool(officer or email),
            "confidence": 0.95 if email else 0.2,
        }

    def _draft_email(self, text: str) -> Dict[str, Any]:
        return {
            "subject": "Request for Erasure of Personal Data under Section 12, DPDPA 2023",
            "body": "Pursuant to Section 12 of the Digital Personal Data Protection Act, 2023, please erase my personal data...",
        }

    def _classify_reply(self, text: str) -> Dict[str, Any]:
        text_lower = text.lower()
        ticket_match = re.search(r"(?:ticket|ref|case|id)[:\s#]*([a-zA-Z0-9-]+)", text, re.IGNORECASE)
        ticket_id = ticket_match.group(1) if ticket_match else None

        if "tax" in text_lower or "statutory" in text_lower or "financial records" in text_lower or "retain" in text_lower:
            return {
                "label": "PARTIAL",
                "ticket_id": ticket_id,
                "retained_items": ["Tax invoices and transaction history"],
                "legal_basis": "Income Tax Act / GST Act requirements",
                "retention_period": "7 years",
                "plain_explanation": "Company erased user profile but must retain tax invoices per statutory law.",
            }
        elif "cannot delete" in text_lower or "refuse" in text_lower or "rejected" in text_lower:
            return {
                "label": "REFUSED",
                "ticket_id": ticket_id,
                "plain_explanation": "Company refused the erasure request.",
            }
        elif "verify your identity" in text_lower or "send id" in text_lower or "more information" in text_lower:
            return {
                "label": "NEEDS_INFO",
                "ticket_id": ticket_id,
                "needs_info_detail": "Company requested identity verification.",
                "plain_explanation": "Please log into the service directly or verify identity through their official channel.",
            }
        elif "deleted" in text_lower or "erased" in text_lower or "successfully closed" in text_lower:
            return {
                "label": "RESOLVED",
                "ticket_id": ticket_id,
                "retained_items": [],
                "plain_explanation": "Company confirmed complete erasure of personal data.",
            }
        elif "acknowledg" in text_lower or "received your request" in text_lower:
            return {
                "label": "ACKNOWLEDGED",
                "ticket_id": ticket_id,
                "plain_explanation": "Company acknowledged receipt and opened a ticket.",
            }
        else:
            return {
                "label": "IRRELEVANT",
                "ticket_id": None,
                "plain_explanation": "Message is unrelated to the erasure request.",
            }

    def _draft_escalation(self, text: str) -> Dict[str, Any]:
        return {
            "subject": "Grievance Redressal Complaint to Data Protection Board of India",
            "timeline": ["Day 0: Initial request sent", "Day 30: Follow-up sent", "Day 60: Escalation drafted"],
            "relief_sought": ["Direct Data Fiduciary to erase personal data", "Require written disclosure of retained data"],
            "body": "Formal complaint submitted to the Data Protection Board of India under Section 13(3)...",
        }
