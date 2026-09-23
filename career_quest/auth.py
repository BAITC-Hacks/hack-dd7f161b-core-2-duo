"""Demo credentials and server-verified sessions, independent of the HTTP layer."""

import base64
import binascii
import hashlib
import hmac
import json
import os
import secrets
import threading
import time
from dataclasses import dataclass
from typing import Literal, Protocol

from career_quest.dataset import Dataset

# Local demo only. Production MUST set AUTH_SECRET to a strong shared secret on all instances.
DEV_AUTH_SECRET = "career-quest-local-demo-only-change-in-production"
SESSION_TTL_SECONDS = 8 * 60 * 60


@dataclass(frozen=True)
class Principal:
    role: Literal["employee", "hr"]
    employee_id: str | None
    expires_at: int
    jti: str


class SessionStore(Protocol):
    """Authentication boundary used by routes.

    A future PostgresSessionStore can check password hashes in auth_users and
    create/resolve/revoke rows in auth_sessions (e.g. via SQLAlchemy), returning
    the same opaque token and Principal without changing routes or the UI.
    """

    def create(self, login: str, password: str, dataset: Dataset) -> str | None: ...

    def resolve(self, token: str) -> Principal | None: ...

    def revoke(self, token: str) -> None: ...


def _encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _decode(value: str) -> bytes:
    raw = value.encode("ascii")
    decoded = base64.b64decode(raw + b"=" * (-len(raw) % 4), altchars=b"-_", validate=True)
    if _encode(decoded) != value:
        raise ValueError("Non-canonical base64url")
    return decoded


class SignedTokenStore:
    """Stateless HMAC-SHA256 sessions, valid on every instance sharing AUTH_SECRET.

    Only revoked jtis are held locally, never the issued tokens. Revocation is
    best-effort on serverless: another instance/cold start may accept a revoked
    token until its expiry. Use shared storage for guaranteed global logout.
    """

    def __init__(self, secret: str | None = None, ttl_seconds: int = SESSION_TTL_SECONDS):
        self._secret = secret if secret is not None else os.getenv("AUTH_SECRET") or DEV_AUTH_SECRET
        self._key = self._secret.encode("utf-8")
        self._ttl_seconds = ttl_seconds
        self._revoked: dict[str, int] = {}
        self._lock = threading.Lock()

    def create(self, login: str, password: str, dataset: Dataset) -> str | None:
        login = login.strip()
        is_hr = login == "hr"
        expected = (
            os.getenv("DEMO_HR_PASSWORD", "hr-demo")
            if is_hr
            else os.getenv("DEMO_EMPLOYEE_PASSWORD", "demo")
        )
        try:
            password_matches = hmac.compare_digest(
                password.encode("utf-8"), expected.encode("utf-8")
            )
        except UnicodeError:
            return None
        if not password_matches or (not is_hr and login not in dataset.employees):
            return None
        payload = {
            "role": "hr" if is_hr else "employee",
            "employee_id": None if is_hr else login,
            "exp": int(time.time()) + self._ttl_seconds,
            "jti": secrets.token_urlsafe(24),
        }
        encoded = _encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
        signature = hmac.new(self._key, encoded.encode("ascii"), hashlib.sha256).digest()
        return f"{encoded}.{_encode(signature)}"

    def resolve(self, token: str) -> Principal | None:
        if not isinstance(token, str) or len(token) > 4096:
            return None
        try:
            encoded, signature = token.split(".")
            expected = hmac.new(self._key, encoded.encode("ascii"), hashlib.sha256).digest()
            if not hmac.compare_digest(_decode(signature), expected):
                return None
            payload = json.loads(_decode(encoded))
        except (ValueError, UnicodeError, binascii.Error, RecursionError):
            return None
        if not isinstance(payload, dict):
            return None
        role = payload.get("role")
        employee_id = payload.get("employee_id")
        expiry = payload.get("exp")
        jti = payload.get("jti")
        if role not in ("employee", "hr"):
            return None
        if role == "employee" and (not isinstance(employee_id, str) or not employee_id):
            return None
        if role == "hr" and employee_id is not None:
            return None
        if type(expiry) is not int or expiry <= time.time():
            return None
        if not isinstance(jti, str) or not jti:
            return None
        with self._lock:
            if jti in self._revoked:
                return None
        return Principal(role=role, employee_id=employee_id, expires_at=expiry, jti=jti)

    def revoke(self, token: str) -> None:
        principal = self.resolve(token)
        if principal is None:
            return
        now = time.time()
        with self._lock:
            self._revoked = {jti: exp for jti, exp in self._revoked.items() if exp > now}
            self._revoked[principal.jti] = principal.expires_at
