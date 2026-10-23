from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Optional
import yaml
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # ASI1 LLM
    ASI1_API_KEY: str = Field(default="mock-asi1-key")
    ASI1_BASE_URL: str = Field(default="https://api.asi1.ai/v1")
    ASI1_MODEL: str = Field(default="asi1")
    USE_FAKE_ASI1: bool = Field(default=True)

    # Agent Seeds
    CONCIERGE_SEED: str = Field(default="deleteme_concierge_seed")
    DISCOVERY_SEED: str = Field(default="deleteme_discovery_seed")
    DRAFTER_SEED: str = Field(default="deleteme_drafter_seed")
    DISPATCHER_SEED: str = Field(default="deleteme_dispatcher_seed")
    TRACKER_SEED: str = Field(default="deleteme_tracker_seed")
    MOCK_COMPANY_SEED: str = Field(default="deleteme_mock_company_seed")

    # Agent Addresses
    CONCIERGE_ADDR: Optional[str] = None
    DISCOVERY_ADDR: Optional[str] = None
    DRAFTER_ADDR: Optional[str] = None
    DISPATCHER_ADDR: Optional[str] = None
    TRACKER_ADDR: Optional[str] = None
    MOCK_COMPANY_ADDR: Optional[str] = None

    # Agentverse
    AGENTVERSE_API_KEY: Optional[str] = None
    AGENT_MAILBOX_KEY: Optional[str] = None

    # App Settings
    DEBUG_MODE: bool = Field(default=True)
    DEMO_CLOCK_SPEED: float = Field(default=1.0)
    SESSION_TTL_MINUTES: int = Field(default=30)
    APPROVAL_HMAC_SECRET: str = Field(default="default_hmac_secret_for_development_purposes_only")
    PAYMENTS_BYPASS_FOR_DEMO: bool = Field(default=True)

    # Dispatch & SMTP
    SEND_MODE: str = Field(default="dry_run")
    DEMO_RECIPIENT_OVERRIDE: str = Field(default="demo-inbox@example.com")
    CONFIRM_LIVE: bool = Field(default=False)
    REPLY_BASE: str = Field(default="requests@deleteme.local")
    FROM_EMAIL: str = Field(default="deleteme-agent@example.com")
    SMTP_HOST: Optional[str] = None
    SMTP_PORT: int = Field(default=587)
    SMTP_USER: Optional[str] = None
    SMTP_PASS: Optional[str] = None

    # IMAP
    IMAP_ENABLED: bool = Field(default=False)
    IMAP_HOST: Optional[str] = None
    IMAP_PORT: int = Field(default=993)
    IMAP_USER: Optional[str] = None
    IMAP_PASS: Optional[str] = None

    # DB
    DB_PATH: str = Field(default="data/deleteme.db")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


@lru_cache(maxsize=1)
def get_law_config() -> Dict[str, Any]:
    law_file = BASE_DIR / "config" / "law.yaml"
    if not law_file.exists():
        return {}
    with open(law_file, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


@lru_cache(maxsize=1)
def get_pricing_config() -> Dict[str, Any]:
    pricing_file = BASE_DIR / "config" / "pricing.yaml"
    if not pricing_file.exists():
        return {}
    with open(pricing_file, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}
