from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

from shared.clock import now
from shared.config import get_settings
from shared.db import BaseRepository
from shared.models import UserProfile


class SessionState:
    NEW = "NEW"
    NEED_IDENTITY = "NEED_IDENTITY"
    CONFIRM_COMPANIES = "CONFIRM_COMPANIES"
    DISCOVERING = "DISCOVERING"
    DRAFTING = "DRAFTING"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    AWAITING_PAYMENT = "AWAITING_PAYMENT"
    DISPATCHING = "DISPATCHING"
    TRACKING = "TRACKING"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"


class ConciergeSession:
    def __init__(
        self,
        session_id: str,
        state: str = SessionState.NEW,
        user_name: Optional[str] = None,
        user_email: Optional[str] = None,
        user_phone: Optional[str] = None,
        companies: Optional[List[str]] = None,
        batch_id: Optional[str] = None,
        disclaimer_shown: bool = False,
        created_at: Optional[datetime] = None,
        updated_at: Optional[datetime] = None,
        data: Optional[Dict[str, Any]] = None,
    ):
        self.session_id = session_id
        self.state = state
        self.user_name = user_name
        self.user_email = user_email
        self.user_phone = user_phone
        self.companies: List[str] = companies or []
        self.batch_id = batch_id
        self.disclaimer_shown = disclaimer_shown
        self.created_at = created_at or now()
        self.updated_at = updated_at or now()
        self.data: Dict[str, Any] = data or {}

    def is_expired(self, ttl_minutes: Optional[int] = None) -> bool:
        if self.state in [SessionState.CANCELLED, SessionState.EXPIRED, SessionState.TRACKING]:
            return False
        ttl = ttl_minutes or get_settings().SESSION_TTL_MINUTES
        elapsed = (now() - self.updated_at).total_seconds() / 60.0
        return elapsed > ttl

    def update_timestamp(self) -> None:
        self.updated_at = now()

    def get_user_profile(self) -> Optional[UserProfile]:
        if self.user_name and self.user_email:
            return UserProfile(
                name=self.user_name,
                email=self.user_email,
                phone=self.user_phone,
                identifiers=self.data.get("identifiers", {}),
            )
        return None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "state": self.state,
            "user_name": self.user_name,
            "user_email": self.user_email,
            "user_phone": self.user_phone,
            "companies": self.companies,
            "batch_id": self.batch_id,
            "disclaimer_shown": self.disclaimer_shown,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "data": self.data,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ConciergeSession":
        inner_data = d.get("data") or {}
        return cls(
            session_id=d["session_id"],
            state=d.get("state", SessionState.NEW),
            user_name=d.get("user_name"),
            user_email=d.get("user_email"),
            user_phone=inner_data.get("user_phone"),
            companies=inner_data.get("companies", []),
            batch_id=inner_data.get("batch_id"),
            disclaimer_shown=inner_data.get("disclaimer_shown", False),
            created_at=datetime.fromisoformat(d["created_at"]) if "created_at" in d else None,
            updated_at=datetime.fromisoformat(d["updated_at"]) if "updated_at" in d else None,
            data=inner_data,
        )


def load_session(repo: BaseRepository, session_id: str) -> ConciergeSession:
    data = repo.get_session(session_id)
    if data:
        sess = ConciergeSession.from_dict(data)
        if sess.is_expired():
            sess.state = SessionState.EXPIRED
            save_session(repo, sess)
        return sess
    new_sess = ConciergeSession(session_id=session_id)
    save_session(repo, new_sess)
    return new_sess


def save_session(repo: BaseRepository, sess: ConciergeSession) -> None:
    sess.update_timestamp()
    meta = {
        "companies": sess.companies,
        "batch_id": sess.batch_id,
        "user_phone": sess.user_phone,
        "disclaimer_shown": sess.disclaimer_shown,
        **sess.data,
    }
    repo.save_session(
        session_id=sess.session_id,
        state=sess.state,
        user_name=sess.user_name,
        user_email=sess.user_email,
        data=meta,
    )
