"""Profile tools: let ULTRON learn and recall who you are."""
from __future__ import annotations

from .. import profile
from . import tool


@tool(
    "remember",
    "Store a lasting fact about the user so ULTRON remembers it forever.",
    {"fact": "the thing to remember, e.g. 'I am a full-stack developer'"},
)
def remember(fact: str) -> str:
    return profile.add_fact(fact)


@tool(
    "set_preference",
    "Record how the user likes ULTRON to behave.",
    {"preference": "e.g. 'keep answers short' or 'call me boss'"},
)
def set_preference(preference: str) -> str:
    return profile.add_preference(preference)


@tool(
    "update_profile",
    "Update a core profile field about the user.",
    {"field": "one of: name, email, role, location, about", "value": "the new value"},
)
def update_profile(field: str, value: str) -> str:
    return profile.set_field(field, value)


@tool("whoami", "Recall everything ULTRON knows about the user.", {})
def whoami() -> str:
    return profile.profile_prompt()
