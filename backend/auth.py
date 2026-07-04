"""
Multi-user authentication for ULTRON.

- Passwords are salted + hashed with PBKDF2 (stdlib, no extra deps).
- Login issues a signed token that encodes the user id, verified on every
  request and WebSocket connection.
- The very first account created becomes the admin.
"""
from __future__ import annotations

import hashlib
import hmac
import re
import secrets
import time

from . import memory
from .config import settings

_SECRET = (settings.secret_key or secrets.token_hex(32)).encode()
TOKEN_TTL = 60 * 60 * 24 * 30  # 30 days
_PBKDF2_ROUNDS = 200_000

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


# ----------------------------- passwords ----------------------------

def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), _PBKDF2_ROUNDS)
    return f"{salt}${dk.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        salt, expected = stored.split("$", 1)
    except ValueError:
        return False
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), _PBKDF2_ROUNDS)
    return hmac.compare_digest(dk.hex(), expected)


# ------------------------------- tokens -----------------------------

def _sign(payload: str) -> str:
    return hmac.new(_SECRET, payload.encode(), hashlib.sha256).hexdigest()


def issue_token(user_id: int) -> str:
    expiry = str(int(time.time()) + TOKEN_TTL)
    payload = f"{user_id}.{expiry}"
    return f"{payload}.{_sign(payload)}"


def verify_token(token: str | None) -> int | None:
    """Return the user id for a valid token, else None."""
    if not token or token.count(".") != 2:
        return None
    uid, expiry, sig = token.split(".")
    if not hmac.compare_digest(sig, _sign(f"{uid}.{expiry}")):
        return None
    try:
        if int(expiry) <= time.time():
            return None
        return int(uid)
    except ValueError:
        return None


# --------------------------- registration ---------------------------

def register(email: str, password: str) -> tuple[dict | None, str]:
    """Create an account. Returns (user, error_message)."""
    email = (email or "").strip().lower()
    if not EMAIL_RE.match(email):
        return None, "Please enter a valid email address."
    if len(password or "") < 6:
        return None, "Password must be at least 6 characters."
    if memory.get_user_by_email(email):
        return None, "An account with that email already exists."
    is_admin = memory.count_users() == 0  # first user runs the show
    uid = memory.create_user(email, hash_password(password), is_admin)
    if uid is None:
        return None, "Could not create account."
    return memory.get_user(uid), ""


def authenticate(email: str, password: str) -> tuple[dict | None, str]:
    """Validate credentials. Returns (user, error_message)."""
    user = memory.get_user_by_email((email or "").strip().lower())
    if not user or not verify_password(password or "", user["password_hash"]):
        return None, "Wrong email or password."
    if user.get("disabled"):
        return None, "This account has been disabled."
    memory.touch_user(user["id"])
    return user, ""
