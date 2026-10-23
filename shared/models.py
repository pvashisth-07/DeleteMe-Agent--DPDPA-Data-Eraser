from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from uagents import Model


# ==============================================================================
# Domain Data Models (uAgents Model subclasses for inter-agent communication)
# ==============================================================================

class UserProfile(Model):
    name: str
    email: str
    phone: Optional[str] = None
    identifiers: Optional[Dict[str, str]] = None


class DiscoveryRequest(Model):
    session_id: str
    batch_id: str
    company_name: str
    domain: Optional[str] = None
    policy_url: Optional[str] = None


class DiscoveryResult(Model):
    session_id: str
    batch_id: str
    company_name: str
    officer_name: Optional[str] = None
    email: str
    address: Optional[str] = None
    source_url: Optional[str] = None
    verified: bool = False
    error: Optional[str] = None


class DraftRequest(Model):
    session_id: str
    batch_id: str
    request_id: str
    company_name: str
    recipient_email: str
    user_profile: UserProfile
    verified: bool = False


class DraftResult(Model):
    session_id: str
    batch_id: str
    request_id: str
    company_name: str
    recipient_email: str
    subject: str
    body: str
    content_hash: str
    verified: bool = False


class DispatchRequest(Model):
    session_id: str
    batch_id: str
    request_id: str
    company_name: str
    recipient_email: str
    subject: str
    body: str
    approval_token: str
    content_hash: str
    user_email: str
    payment_ref: Optional[str] = None


class DispatchResult(Model):
    session_id: str
    batch_id: str
    request_id: str
    company_name: str
    status: str  # 'SENT', 'SEND_FAILED'
    message_id: Optional[str] = None
    sent_at: Optional[str] = None
    deadline_at: Optional[str] = None
    error: Optional[str] = None


class TrackRequest(Model):
    session_id: str
    batch_id: str
    request_id: str
    company_name: str
    recipient_email: str
    user_email: str
    sent_at: str
    deadline_at: str
    subject: str
    payment_ref: Optional[str] = None


class InboundReply(Model):
    session_id: Optional[str] = None
    batch_id: Optional[str] = None
    request_id: str
    company_name: str
    from_email: str
    subject: str
    body: str
    received_at: str


class StatusUpdate(Model):
    session_id: str
    batch_id: str
    request_id: str
    company_name: str
    state: str
    ticket_id: Optional[str] = None
    details: Optional[str] = None
    updated_at: str


# ==============================================================================
# Internal Pydantic Schemas (Used for ASI1 LLM Structured JSON Extraction)
# ==============================================================================

class IntentExtraction(BaseModel):
    intent: str = Field(description="delete | status | approve | edit | remove | cancel | debug | reply_paste | other")
    companies: List[str] = Field(default_factory=list)
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    identifiers: Dict[str, str] = Field(default_factory=dict)
    raw_parameters: Dict[str, Any] = Field(default_factory=dict)


class ContactExtraction(BaseModel):
    officer_name: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    found_rule9_contact: bool = False
    confidence: float = 0.0


class EmailDraft(BaseModel):
    subject: str
    body: str


class ReplyClassification(BaseModel):
    label: str = Field(description="ACKNOWLEDGED | RESOLVED | PARTIAL | REFUSED | NEEDS_INFO | IRRELEVANT")
    ticket_id: Optional[str] = None
    retained_items: List[str] = Field(default_factory=list)
    legal_basis: Optional[str] = None
    retention_period: Optional[str] = None
    needs_info_detail: Optional[str] = None
    plain_explanation: Optional[str] = None


class EscalationDraft(BaseModel):
    subject: str
    timeline: List[str] = Field(default_factory=list)
    relief_sought: List[str] = Field(default_factory=list)
    body: str
