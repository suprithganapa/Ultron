"""
Authentication for ULTRON.

A lightweight, dependency-free scheme: the user logs in with a password,
and receives a signed (HMAC) token that is checked on every API call and
WebSocket connection. Good enough to keep a public deployment private,
without dragging in a heavy auth framework.

Set ULTRON_PASSWORD (and ideally ULTRON_SECRET) in the environment.
"""
from __future__ import annotations

import hashlib
import hmac
import secrets
import time

from .config import settings

# A stable secret is required to sign tokens. If the operator didn't set one,
# generate a random one for this process (tokens then reset on restart).
_SECRET = (settings.secret_key or secrets.token_hex(32)).encode()

TOKEN_TTL = 60 * 60 * 24 * 30  # 30 days


def _sign(payload: str) -> str:
    return hmac.new(_SECRET, payload.encode(), hashlib.sha256).hexdigest()


def issue_token() -> str:
    """Create a signed token: '<expiry>.<signature>'."""
    expiry = str(int(time.time()) + TOKEN_TTL)
    return f"{expiry}.{_sign(expiry)}"


def verify_token(token: str | None) -> bool:
    if not token or "." not in token:
        return False
    expiry, sig = token.rsplit(".", 1)
    if not hmac.compare_digest(sig, _sign(expiry)):
        return False
    try:
        return int(expiry) > time.time()
    except ValueError:
        return False


def check_password(candidate: str) -> bool:
    if not settings.password:
        return False
    return hmac.compare_digest(candidate.strip(), settings.password)
