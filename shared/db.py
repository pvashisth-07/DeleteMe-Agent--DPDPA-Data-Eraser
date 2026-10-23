import json
import sqlite3
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List, Optional
from shared.clock import now_iso


class BaseRepository(ABC):
    @abstractmethod
    def save_session(self, session_id: str, state: str, user_name: Optional[str] = None, user_email: Optional[str] = None, data: Optional[Dict[str, Any]] = None) -> None:
        pass

    @abstractmethod
    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        pass

    @abstractmethod
    def save_batch(self, batch_id: str, session_id: str, content_hash: str, status: str, approval_token: Optional[str] = None) -> None:
        pass

    @abstractmethod
    def get_batch(self, batch_id: str) -> Optional[Dict[str, Any]]:
        pass

    @abstractmethod
    def save_draft(self, request_id: str, batch_id: str, session_id: str, company_name: str, recipient_email: str, subject: str, body: str, content_hash: str, verified: bool) -> None:
        pass

    @abstractmethod
    def get_drafts_for_batch(self, batch_id: str) -> List[Dict[str, Any]]:
        pass

    @abstractmethod
    def save_request(self, request_id: str, batch_id: str, session_id: str, company_name: str, recipient_email: str, user_email: str, subject: str, body: str, state: str, sent_at: str, deadline_at: str) -> None:
        pass

    @abstractmethod
    def update_request_state(self, request_id: str, state: str, ticket_id: Optional[str] = None, reason: Optional[str] = None) -> None:
        pass

    @abstractmethod
    def get_request(self, request_id: str) -> Optional[Dict[str, Any]]:
        pass

    @abstractmethod
    def get_all_open_requests(self) -> List[Dict[str, Any]]:
        pass

    @abstractmethod
    def record_event(self, request_id: str, batch_id: str, session_id: str, from_state: str, to_state: str, reason: str = "", payload: Optional[Dict[str, Any]] = None) -> None:
        pass

    @abstractmethod
    def get_events_for_request(self, request_id: str) -> List[Dict[str, Any]]:
        pass

    @abstractmethod
    def save_payment(self, payment_id: str, payer: str, payee: str, amount: str, currency: str, purpose: str, ref: str, status: str) -> None:
        pass

    @abstractmethod
    def get_cached_contact(self, company_key: str) -> Optional[Dict[str, Any]]:
        pass

    @abstractmethod
    def set_cached_contact(self, company_key: str, officer_name: Optional[str], email: str, address: Optional[str], source_url: Optional[str], verified: bool) -> None:
        pass

    @abstractmethod
    def get_cached_policy(self, url: str) -> Optional[str]:
        pass

    @abstractmethod
    def set_cached_policy(self, url: str, html_content: str) -> None:
        pass


class SqliteRepo(BaseRepository):
    def __init__(self, db_path: str = "data/deleteme.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.executescript("""
            CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY,
                user_name TEXT,
                user_email TEXT,
                state TEXT,
                created_at TEXT,
                updated_at TEXT,
                data TEXT
            );

            CREATE TABLE IF NOT EXISTS batches (
                batch_id TEXT PRIMARY KEY,
                session_id TEXT,
                content_hash TEXT,
                approval_token TEXT,
                status TEXT,
                created_at TEXT,
                approved_at TEXT
            );

            CREATE TABLE IF NOT EXISTS drafts (
                request_id TEXT PRIMARY KEY,
                batch_id TEXT,
                session_id TEXT,
                company_name TEXT,
                recipient_email TEXT,
                subject TEXT,
                body TEXT,
                content_hash TEXT,
                verified INTEGER,
                created_at TEXT
            );

            CREATE TABLE IF NOT EXISTS requests (
                request_id TEXT PRIMARY KEY,
                batch_id TEXT,
                session_id TEXT,
                company_name TEXT,
                recipient_email TEXT,
                user_email TEXT,
                subject TEXT,
                body TEXT,
                state TEXT,
                ticket_id TEXT,
                sent_at TEXT,
                deadline_at TEXT,
                last_reply_at TEXT,
                updated_at TEXT
            );

            CREATE TABLE IF NOT EXISTS events (
                event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                request_id TEXT,
                batch_id TEXT,
                session_id TEXT,
                from_state TEXT,
                to_state TEXT,
                reason TEXT,
                payload TEXT,
                timestamp TEXT
            );

            CREATE TABLE IF NOT EXISTS payments (
                payment_id TEXT PRIMARY KEY,
                payer TEXT,
                payee TEXT,
                amount TEXT,
                currency TEXT,
                purpose TEXT,
                ref TEXT,
                status TEXT,
                timestamp TEXT
            );

            CREATE TABLE IF NOT EXISTS contacts_cache (
                company_key TEXT PRIMARY KEY,
                officer_name TEXT,
                email TEXT,
                address TEXT,
                source_url TEXT,
                verified INTEGER,
                updated_at TEXT
            );

            CREATE TABLE IF NOT EXISTS policy_cache (
                url TEXT PRIMARY KEY,
                html_content TEXT,
                fetched_at TEXT
            );
            """)
            conn.commit()

    def save_session(self, session_id: str, state: str, user_name: Optional[str] = None, user_email: Optional[str] = None, data: Optional[Dict[str, Any]] = None) -> None:
        ts = now_iso()
        data_json = json.dumps(data or {})
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO sessions (session_id, user_name, user_email, state, created_at, updated_at, data)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(session_id) DO UPDATE SET
                    user_name = COALESCE(excluded.user_name, sessions.user_name),
                    user_email = COALESCE(excluded.user_email, sessions.user_email),
                    state = excluded.state,
                    updated_at = excluded.updated_at,
                    data = excluded.data
            """, (session_id, user_name, user_email, state, ts, ts, data_json))
            conn.commit()

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM sessions WHERE session_id = ?", (session_id,))
            row = cursor.fetchone()
            if not row:
                return None
            res = dict(row)
            res["data"] = json.loads(res.get("data") or "{}")
            return res

    def save_batch(self, batch_id: str, session_id: str, content_hash: str, status: str, approval_token: Optional[str] = None) -> None:
        ts = now_iso()
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO batches (batch_id, session_id, content_hash, approval_token, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(batch_id) DO UPDATE SET
                    content_hash = excluded.content_hash,
                    approval_token = COALESCE(excluded.approval_token, batches.approval_token),
                    status = excluded.status,
                    approved_at = CASE WHEN excluded.status = 'APPROVED' THEN excluded.created_at ELSE batches.approved_at END
            """, (batch_id, session_id, content_hash, approval_token, status, ts))
            conn.commit()

    def get_batch(self, batch_id: str) -> Optional[Dict[str, Any]]:
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM batches WHERE batch_id = ?", (batch_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def save_draft(self, request_id: str, batch_id: str, session_id: str, company_name: str, recipient_email: str, subject: str, body: str, content_hash: str, verified: bool) -> None:
        ts = now_iso()
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO drafts (request_id, batch_id, session_id, company_name, recipient_email, subject, body, content_hash, verified, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(request_id) DO UPDATE SET
                    subject = excluded.subject,
                    body = excluded.body,
                    content_hash = excluded.content_hash,
                    verified = excluded.verified
            """, (request_id, batch_id, session_id, company_name, recipient_email, subject, body, content_hash, 1 if verified else 0, ts))
            conn.commit()

    def get_drafts_for_batch(self, batch_id: str) -> List[Dict[str, Any]]:
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM drafts WHERE batch_id = ?", (batch_id,))
            rows = cursor.fetchall()
            return [dict(r) for r in rows]

    def save_request(self, request_id: str, batch_id: str, session_id: str, company_name: str, recipient_email: str, user_email: str, subject: str, body: str, state: str, sent_at: str, deadline_at: str) -> None:
        ts = now_iso()
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO requests (request_id, batch_id, session_id, company_name, recipient_email, user_email, subject, body, state, sent_at, deadline_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(request_id) DO UPDATE SET
                    state = excluded.state,
                    updated_at = excluded.updated_at
            """, (request_id, batch_id, session_id, company_name, recipient_email, user_email, subject, body, state, sent_at, deadline_at, ts))
            conn.commit()

    def update_request_state(self, request_id: str, state: str, ticket_id: Optional[str] = None, reason: Optional[str] = None) -> None:
        ts = now_iso()
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT state, batch_id, session_id FROM requests WHERE request_id = ?", (request_id,))
            row = cursor.fetchone()
            from_state = row["state"] if row else "UNKNOWN"
            batch_id = row["batch_id"] if row else ""
            session_id = row["session_id"] if row else ""

            cursor.execute("""
                UPDATE requests
                SET state = ?,
                    ticket_id = COALESCE(?, ticket_id),
                    updated_at = ?
                WHERE request_id = ?
            """, (state, ticket_id, ts, request_id))

            cursor.execute("""
                INSERT INTO events (request_id, batch_id, session_id, from_state, to_state, reason, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (request_id, batch_id, session_id, from_state, state, reason or "", ts))
            conn.commit()

    def get_request(self, request_id: str) -> Optional[Dict[str, Any]]:
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM requests WHERE request_id = ?", (request_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_all_open_requests(self) -> List[Dict[str, Any]]:
        # Non-terminal states
        terminal_states = ("RESOLVED", "PARTIAL", "REFUSED", "SEND_FAILED")
        placeholders = ",".join("?" * len(terminal_states))
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute(f"SELECT * FROM requests WHERE state NOT IN ({placeholders})", terminal_states)
            rows = cursor.fetchall()
            return [dict(r) for r in rows]

    def record_event(self, request_id: str, batch_id: str, session_id: str, from_state: str, to_state: str, reason: str = "", payload: Optional[Dict[str, Any]] = None) -> None:
        ts = now_iso()
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO events (request_id, batch_id, session_id, from_state, to_state, reason, payload, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (request_id, batch_id, session_id, from_state, to_state, reason, json.dumps(payload or {}), ts))
            conn.commit()

    def get_events_for_request(self, request_id: str) -> List[Dict[str, Any]]:
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM events WHERE request_id = ? ORDER BY event_id ASC", (request_id,))
            rows = cursor.fetchall()
            return [dict(r) for r in rows]

    def save_payment(self, payment_id: str, payer: str, payee: str, amount: str, currency: str, purpose: str, ref: str, status: str) -> None:
        ts = now_iso()
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO payments (payment_id, payer, payee, amount, currency, purpose, ref, status, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (payment_id, payer, payee, amount, currency, purpose, ref, status, ts))
            conn.commit()

    def get_cached_contact(self, company_key: str) -> Optional[Dict[str, Any]]:
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM contacts_cache WHERE company_key = ?", (company_key.lower(),))
            row = cursor.fetchone()
            return dict(row) if row else None

    def set_cached_contact(self, company_key: str, officer_name: Optional[str], email: str, address: Optional[str], source_url: Optional[str], verified: bool) -> None:
        ts = now_iso()
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO contacts_cache (company_key, officer_name, email, address, source_url, verified, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(company_key) DO UPDATE SET
                    officer_name = excluded.officer_name,
                    email = excluded.email,
                    address = excluded.address,
                    source_url = excluded.source_url,
                    verified = excluded.verified,
                    updated_at = excluded.updated_at
            """, (company_key.lower(), officer_name, email, address, source_url, 1 if verified else 0, ts))
            conn.commit()

    def get_cached_policy(self, url: str) -> Optional[str]:
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT html_content FROM policy_cache WHERE url = ?", (url,))
            row = cursor.fetchone()
            return row["html_content"] if row else None

    def set_cached_policy(self, url: str, html_content: str) -> None:
        ts = now_iso()
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO policy_cache (url, html_content, fetched_at)
                VALUES (?, ?, ?)
                ON CONFLICT(url) DO UPDATE SET
                    html_content = excluded.html_content,
                    fetched_at = excluded.fetched_at
            """, (url, html_content, ts))
            conn.commit()


class CtxStorageRepo(BaseRepository):
    """Adapter storing data in uAgents agent context storage (or memory dict)."""

    def __init__(self, storage_dict: Optional[Dict[str, Any]] = None):
        self._store = storage_dict if storage_dict is not None else {}

    def save_session(self, session_id: str, state: str, user_name: Optional[str] = None, user_email: Optional[str] = None, data: Optional[Dict[str, Any]] = None) -> None:
        ts = now_iso()
        curr = self._store.get(f"session:{session_id}", {})
        curr.update({
            "session_id": session_id,
            "state": state,
            "user_name": user_name or curr.get("user_name"),
            "user_email": user_email or curr.get("user_email"),
            "updated_at": ts,
            "data": data or curr.get("data", {}),
        })
        if "created_at" not in curr:
            curr["created_at"] = ts
        self._store[f"session:{session_id}"] = curr

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        return self._store.get(f"session:{session_id}")

    def save_batch(self, batch_id: str, session_id: str, content_hash: str, status: str, approval_token: Optional[str] = None) -> None:
        ts = now_iso()
        curr = self._store.get(f"batch:{batch_id}", {})
        curr.update({
            "batch_id": batch_id,
            "session_id": session_id,
            "content_hash": content_hash,
            "status": status,
            "approval_token": approval_token or curr.get("approval_token"),
        })
        if "created_at" not in curr:
            curr["created_at"] = ts
        if status == "APPROVED":
            curr["approved_at"] = ts
        self._store[f"batch:{batch_id}"] = curr

    def get_batch(self, batch_id: str) -> Optional[Dict[str, Any]]:
        return self._store.get(f"batch:{batch_id}")

    def save_draft(self, request_id: str, batch_id: str, session_id: str, company_name: str, recipient_email: str, subject: str, body: str, content_hash: str, verified: bool) -> None:
        self._store[f"draft:{request_id}"] = {
            "request_id": request_id,
            "batch_id": batch_id,
            "session_id": session_id,
            "company_name": company_name,
            "recipient_email": recipient_email,
            "subject": subject,
            "body": body,
            "content_hash": content_hash,
            "verified": 1 if verified else 0,
            "created_at": now_iso(),
        }

    def get_drafts_for_batch(self, batch_id: str) -> List[Dict[str, Any]]:
        return [v for k, v in self._store.items() if k.startswith("draft:") and v.get("batch_id") == batch_id]

    def save_request(self, request_id: str, batch_id: str, session_id: str, company_name: str, recipient_email: str, user_email: str, subject: str, body: str, state: str, sent_at: str, deadline_at: str) -> None:
        self._store[f"req:{request_id}"] = {
            "request_id": request_id,
            "batch_id": batch_id,
            "session_id": session_id,
            "company_name": company_name,
            "recipient_email": recipient_email,
            "user_email": user_email,
            "subject": subject,
            "body": body,
            "state": state,
            "sent_at": sent_at,
            "deadline_at": deadline_at,
            "updated_at": now_iso(),
        }

    def update_request_state(self, request_id: str, state: str, ticket_id: Optional[str] = None, reason: Optional[str] = None) -> None:
        req = self._store.get(f"req:{request_id}")
        if req:
            from_state = req.get("state", "UNKNOWN")
            req["state"] = state
            if ticket_id:
                req["ticket_id"] = ticket_id
            req["updated_at"] = now_iso()
            self.record_event(request_id, req.get("batch_id", ""), req.get("session_id", ""), from_state, state, reason or "")

    def get_request(self, request_id: str) -> Optional[Dict[str, Any]]:
        return self._store.get(f"req:{request_id}")

    def get_all_open_requests(self) -> List[Dict[str, Any]]:
        terminal = ("RESOLVED", "PARTIAL", "REFUSED", "SEND_FAILED")
        return [v for k, v in self._store.items() if k.startswith("req:") and v.get("state") not in terminal]

    def record_event(self, request_id: str, batch_id: str, session_id: str, from_state: str, to_state: str, reason: str = "", payload: Optional[Dict[str, Any]] = None) -> None:
        events = self._store.setdefault("events_list", [])
        events.append({
            "event_id": len(events) + 1,
            "request_id": request_id,
            "batch_id": batch_id,
            "session_id": session_id,
            "from_state": from_state,
            "to_state": to_state,
            "reason": reason,
            "payload": json.dumps(payload or {}),
            "timestamp": now_iso(),
        })

    def get_events_for_request(self, request_id: str) -> List[Dict[str, Any]]:
        events = self._store.get("events_list", [])
        return [e for e in events if e.get("request_id") == request_id]

    def save_payment(self, payment_id: str, payer: str, payee: str, amount: str, currency: str, purpose: str, ref: str, status: str) -> None:
        self._store[f"pay:{payment_id}"] = {
            "payment_id": payment_id,
            "payer": payer,
            "payee": payee,
            "amount": amount,
            "currency": currency,
            "purpose": purpose,
            "ref": ref,
            "status": status,
            "timestamp": now_iso(),
        }

    def get_cached_contact(self, company_key: str) -> Optional[Dict[str, Any]]:
        return self._store.get(f"contact:{company_key.lower()}")

    def set_cached_contact(self, company_key: str, officer_name: Optional[str], email: str, address: Optional[str], source_url: Optional[str], verified: bool) -> None:
        self._store[f"contact:{company_key.lower()}"] = {
            "company_key": company_key.lower(),
            "officer_name": officer_name,
            "email": email,
            "address": address,
            "source_url": source_url,
            "verified": 1 if verified else 0,
            "updated_at": now_iso(),
        }

    def get_cached_policy(self, url: str) -> Optional[str]:
        return self._store.get(f"policy:{url}")

    def set_cached_policy(self, url: str, html_content: str) -> None:
        self._store[f"policy:{url}"] = html_content
