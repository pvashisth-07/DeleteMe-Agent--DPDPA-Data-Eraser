import uuid
from typing import Optional
from uagents_core.contrib.protocols.payment import (
    CommitPayment,
    CompletePayment,
    Funds,
    RejectPayment,
    RequestPayment,
    payment_protocol_spec,
)
from shared.clock import now_iso
from shared.db import BaseRepository
from shared.logging import global_trace_collector, setup_logger

logger = setup_logger("payments")


def create_payment_request(
    recipient: str,
    amount: str,
    currency: str = "atestfet",
    reference: str = "",
    description: str = "DPDPA Deletion Service Fee",
    deadline_seconds: int = 3600,
) -> RequestPayment:
    funds = Funds(amount=amount, currency=currency, payment_method="native")
    return RequestPayment(
        accepted_funds=[funds],
        recipient=recipient,
        deadline_seconds=deadline_seconds,
        reference=reference,
        description=description,
        metadata={"created_at": now_iso()},
    )


def commit_payment(
    recipient: str,
    amount: str,
    currency: str = "atestfet",
    reference: str = "",
    description: str = "DPDPA Service Payment",
    transaction_id: Optional[str] = None,
) -> CommitPayment:
    tx_id = transaction_id or f"tx_{uuid.uuid4().hex[:12]}"
    funds = Funds(amount=amount, currency=currency, payment_method="native")
    return CommitPayment(
        funds=funds,
        recipient=recipient,
        transaction_id=tx_id,
        reference=reference,
        description=description,
        metadata={"committed_at": now_iso()},
    )


def record_payment_in_db(
    repo: BaseRepository,
    payer: str,
    payee: str,
    amount: str,
    currency: str,
    purpose: str,
    ref: str,
    status: str,
    payment_id: Optional[str] = None,
) -> str:
    pid = payment_id or f"pay_{uuid.uuid4().hex[:12]}"
    repo.save_payment(
        payment_id=pid,
        payer=payer,
        payee=payee,
        amount=amount,
        currency=currency,
        purpose=purpose,
        ref=ref,
        status=status,
    )
    global_trace_collector.record_payment(
        payer=payer,
        payee=payee,
        amount=amount,
        currency=currency,
        purpose=purpose,
        ref=ref,
        status=status,
    )
    return pid


def is_payment_authorized(
    payment_ref: Optional[str],
    bypass_for_demo: bool = True,
) -> bool:
    if bypass_for_demo:
        return True
    return bool(payment_ref and len(payment_ref) > 3)
