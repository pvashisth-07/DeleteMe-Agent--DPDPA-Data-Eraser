import asyncio
import email
from email.header import decode_header
import imaplib
import re
from typing import Any, Dict, List, Optional, Tuple

from shared.clock import now_iso
from shared.config import get_settings
from shared.db import BaseRepository, SqliteRepo
from shared.logging import setup_logger
from shared.models import InboundReply

logger = setup_logger("imap_poller")

# Regex to extract request_id from plus-addressed email: e.g. requests+req_12345@domain.com
PLUS_ADDRESS_REGEX = re.compile(r"\+([a-zA-Z0-9_\-]+)@", re.IGNORECASE)


def extract_request_id_from_recipient(recipient_str: str) -> Optional[str]:
    """
    Extracts request_id from a plus-addressed email header (e.g. requests+req_abc123@domain.in).
    """
    if not recipient_str:
        return None
    match = PLUS_ADDRESS_REGEX.search(recipient_str)
    return match.group(1).strip() if match else None


def decode_mime_header(header_val: Optional[str]) -> str:
    """Decodes MIME-encoded email headers safely."""
    if not header_val:
        return ""
    decoded_fragments = []
    for fragment, charset in decode_header(header_val):
        if isinstance(fragment, bytes):
            decoded_fragments.append(fragment.decode(charset or "utf-8", errors="replace"))
        else:
            decoded_fragments.append(str(fragment))
    return " ".join(decoded_fragments).strip()


def extract_body_from_email_message(msg: email.message.Message) -> str:
    """Extracts plain text body from standard email message."""
    body_text = ""
    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            content_disposition = str(part.get("Content-Disposition"))
            if content_type == "text/plain" and "attachment" not in content_disposition:
                payload = part.get_payload(decode=True)
                if payload:
                    body_text += payload.decode("utf-8", errors="replace") + "\n"
            elif content_type == "text/html" and not body_text and "attachment" not in content_disposition:
                payload = part.get_payload(decode=True)
                if payload:
                    html_str = payload.decode("utf-8", errors="replace")
                    # Basic tag stripping
                    clean_str = re.sub(r"<[^>]+>", " ", html_str)
                    body_text += clean_str + "\n"
    else:
        payload = msg.get_payload(decode=True)
        if payload:
            body_text = payload.decode("utf-8", errors="replace")
    return body_text.strip()


def parse_raw_email(raw_email_bytes: bytes, repo: Optional[BaseRepository] = None) -> Optional[InboundReply]:
    """
    Parses raw RFC 822 email bytes into a structured InboundReply model mapped to a request_id.
    """
    msg = email.message_from_bytes(raw_email_bytes)
    to_hdr = decode_mime_header(msg.get("To", ""))
    delivered_to = decode_mime_header(msg.get("Delivered-To", ""))
    x_orig_to = decode_mime_header(msg.get("X-Original-To", ""))
    all_recipients = f"{to_hdr} {delivered_to} {x_orig_to}".strip()

    request_id = extract_request_id_from_recipient(all_recipients)
    if not request_id:
        logger.warning(f"No valid plus-addressed request_id found in headers: {all_recipients}")
        return None

    # Retrieve matching request from DB to get company context
    company_name = "Company"
    session_id = None
    batch_id = None
    if repo:
        req = repo.get_request(request_id)
        if req:
            company_name = req.get("company_name", "Company")
            session_id = req.get("session_id")
            batch_id = req.get("batch_id")

    subject = decode_mime_header(msg.get("Subject", "Re: Data Erasure"))
    from_email = decode_mime_header(msg.get("From", "unknown@domain.com"))
    body = extract_body_from_email_message(msg)

    return InboundReply(
        session_id=session_id,
        batch_id=batch_id,
        request_id=request_id,
        company_name=company_name,
        from_email=from_email,
        subject=subject,
        body=body,
        received_at=now_iso(),
    )


async def poll_imap_inbox(repo: BaseRepository) -> List[InboundReply]:
    """
    Connects to IMAP server, polls for UNSEEN messages, extracts plus-addressed InboundReply items.
    """
    settings = get_settings()
    if not settings.IMAP_ENABLED or not settings.IMAP_HOST or not settings.IMAP_USER or not settings.IMAP_PASS:
        logger.debug("IMAP polling is disabled or credentials not configured.")
        return []

    loop = asyncio.get_running_loop()

    def _sync_fetch() -> List[InboundReply]:
        replies = []
        try:
            mail = imaplib.IMAP4_SSL(settings.IMAP_HOST, settings.IMAP_PORT)
            mail.login(settings.IMAP_USER, settings.IMAP_PASS)
            mail.select("INBOX")

            status, data = mail.search(None, "UNSEEN")
            if status != "OK" or not data[0]:
                mail.logout()
                return []

            mail_ids = data[0].split()
            for m_id in mail_ids:
                res_fetch, msg_data = mail.fetch(m_id, "(RFC822)")
                if res_fetch != "OK":
                    continue
                for response_part in msg_data:
                    if isinstance(response_part, tuple):
                        inbound = parse_raw_email(response_part[1], repo=repo)
                        if inbound:
                            replies.append(inbound)

            mail.logout()
        except Exception as e:
            logger.error(f"IMAP poll error: {e}")
        return replies

    return await loop.run_in_executor(None, _sync_fetch)
