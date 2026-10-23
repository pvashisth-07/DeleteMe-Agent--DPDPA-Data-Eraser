import asyncio
import smtplib
import ssl
from email.message import EmailMessage
from typing import Optional, Tuple
from uuid import uuid4
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from shared.config import get_settings
from shared.logging import setup_logger

logger = setup_logger("dispatcher_mailer")


class MailerError(Exception):
    pass


def build_email_message(
    from_email: str,
    recipient: str,
    subject: str,
    body: str,
    reply_to: str,
    cc_email: Optional[str] = None,
    msg_id: Optional[str] = None,
) -> EmailMessage:
    msg = EmailMessage()
    msg["From"] = from_email
    msg["To"] = recipient
    msg["Subject"] = subject
    msg["Reply-To"] = reply_to
    if cc_email:
        msg["Cc"] = cc_email
    msg["Message-ID"] = msg_id or f"<{uuid4().hex[:16]}@deleteme.local>"
    msg.set_content(body)
    return msg


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=0.5, min=0.5, max=4),
    retry=retry_if_exception_type(smtplib.SMTPException),
    reraise=True,
)
def _send_smtp_sync(msg: EmailMessage, host: str, port: int, user: Optional[str], password: Optional[str]) -> None:
    context = ssl.create_default_context()
    if port == 465:
        with smtplib.SMTP_SSL(host, port, context=context, timeout=8) as server:
            if user and password:
                server.login(user, password)
            server.send_message(msg)
    else:
        with smtplib.SMTP(host, port, timeout=8) as server:
            server.starttls(context=context)
            if user and password:
                server.login(user, password)
            server.send_message(msg)


async def send_email(
    recipient: str,
    subject: str,
    body: str,
    request_id: str,
    user_email: Optional[str] = None,
    mode: Optional[str] = None,
    demo_override: Optional[str] = None,
    confirm_live: Optional[bool] = None,
) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Sends email respecting send modes:
    - 'dry_run': Logs and simulates dispatch (never touches network).
    - 'demo_redirect': Rewrites recipient to demo override; asserts real address is not contacted.
    - 'live': Requires confirm_live=True.
    Returns: (success: bool, message_id: Optional[str], error: Optional[str]).
    """
    settings = get_settings()
    send_mode = (mode or settings.SEND_MODE).lower()
    override = demo_override or settings.DEMO_RECIPIENT_OVERRIDE
    is_live_confirmed = confirm_live if confirm_live is not None else settings.CONFIRM_LIVE

    # Generate plus-addressed Reply-To: <local>+<request_id>@<domain>
    reply_base = settings.REPLY_BASE
    if "@" in reply_base:
        local_part, domain_part = reply_base.split("@", 1)
        reply_to = f"{local_part}+{request_id}@{domain_part}"
    else:
        reply_to = f"requests+{request_id}@deleteme.local"

    msg_id = f"<{uuid4().hex[:16]}@deleteme.local>"
    from_email = settings.FROM_EMAIL

    # Mode 1: dry_run
    if send_mode == "dry_run":
        logger.info(
            f"[DRY_RUN] Dispatched email to {recipient} (Reply-To: {reply_to}, CC: {user_email}) | Subject: {subject}"
        )
        return True, msg_id, None

    # Mode 2: demo_redirect
    if send_mode == "demo_redirect":
        intended_recipient = recipient
        final_recipient = override
        assert final_recipient != intended_recipient, "demo_redirect must rewrite real company email to demo override"

        final_body = (
            f"[DEMO: Intended Recipient: {intended_recipient}]\n"
            f"[DEMO: Mode: demo_redirect | Request ID: {request_id}]\n\n"
            + body
        )
        final_subject = f"[DEMO: to {intended_recipient}] {subject}"

        email_msg = build_email_message(
            from_email=from_email,
            recipient=final_recipient,
            subject=final_subject,
            body=final_body,
            reply_to=reply_to,
            cc_email=user_email,
            msg_id=msg_id,
        )

        # If SMTP settings are provided, attempt live send to the demo inbox; otherwise simulate
        if settings.SMTP_HOST and settings.SMTP_USER:
            try:
                loop = asyncio.get_running_loop()
                await loop.run_in_executor(
                    None,
                    _send_smtp_sync,
                    email_msg,
                    settings.SMTP_HOST,
                    settings.SMTP_PORT,
                    settings.SMTP_USER,
                    settings.SMTP_PASS,
                )
                logger.info(f"[DEMO_REDIRECT] Delivered to demo inbox {final_recipient} (Intended: {intended_recipient})")
                return True, msg_id, None
            except Exception as e:
                logger.error(f"[DEMO_REDIRECT] SMTP send failed: {e}")
                return False, None, str(e)
        else:
            logger.info(f"[DEMO_REDIRECT - Simulated SMTP] Delivered to {final_recipient} (Intended: {intended_recipient})")
            return True, msg_id, None

    # Mode 3: live
    if send_mode == "live":
        if not is_live_confirmed:
            err = "Live dispatch rejected: CONFIRM_LIVE is false. Refusing to send real company email."
            logger.error(err)
            return False, None, err

        if not settings.SMTP_HOST or not settings.SMTP_USER:
            err = "Live dispatch failed: SMTP credentials are not configured in .env."
            logger.error(err)
            return False, None, err

        email_msg = build_email_message(
            from_email=from_email,
            recipient=recipient,
            subject=subject,
            body=body,
            reply_to=reply_to,
            cc_email=user_email,
            msg_id=msg_id,
        )

        try:
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(
                None,
                _send_smtp_sync,
                email_msg,
                settings.SMTP_HOST,
                settings.SMTP_PORT,
                settings.SMTP_USER,
                settings.SMTP_PASS,
            )
            logger.info(f"[LIVE] Dispatched email to {recipient} with Message-ID: {msg_id}")
            return True, msg_id, None
        except Exception as e:
            logger.error(f"[LIVE] SMTP send failed after retries: {e}")
            return False, None, str(e)

    return False, None, f"Unknown SEND_MODE '{send_mode}'"
