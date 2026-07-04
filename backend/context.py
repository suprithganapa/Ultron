"""
Per-request user context.

Tools (notes, tasks, profile, …) need to know *whose* data to touch, but the
agent dispatches them by name without threading a user id through every call.
A context variable set at the start of each agent turn solves this cleanly.
"""
from __future__ import annotations

from contextvars import ContextVar

_current_user: ContextVar[int] = ContextVar("current_user", default=0)


def set_user(user_id: int) -> None:
    _current_user.set(user_id)


def get_user() -> int:
    return _current_user.get()
