"""
ULTRON tool registry.

A tool is just a Python function decorated with @tool. Each declares a
name, a human description, and a parameter hint dict. The agent turns this
registry into the "here are your tools" section of the prompt, and dispatches
tool calls back to these functions.

To add a capability to ULTRON: write a function, decorate it, done.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

REGISTRY: dict[str, "Tool"] = {}


@dataclass
class Tool:
    name: str
    description: str
    params: dict[str, str]
    func: Callable[..., Any]

    def run(self, **kwargs) -> Any:
        return self.func(**kwargs)


def tool(name: str, description: str, params: dict[str, str] | None = None):
    def deco(fn: Callable[..., Any]) -> Callable[..., Any]:
        REGISTRY[name] = Tool(name, description, params or {}, fn)
        return fn
    return deco


def load_all() -> None:
    """Import every tool module so their @tool decorators register."""
    from . import web, system, files, code, personal, profile_tools  # noqa: F401
    # Optional integrations — import defensively so a missing dependency or
    # a syntax issue in one never stops ULTRON from booting.
    for mod in ("google_tools", "spotify_tools"):
        try:
            __import__(f"{__name__}.{mod}", fromlist=[mod])
        except Exception as e:  # pragma: no cover
            print(f"  [tools] optional module '{mod}' not loaded: {e}")


def tool_catalog() -> str:
    """Render the registry as a prompt-friendly catalogue."""
    lines = []
    for t in REGISTRY.values():
        p = ", ".join(f"{k}: {v}" for k, v in t.params.items()) or "no arguments"
        lines.append(f"- {t.name}({p}) — {t.description}")
    return "\n".join(lines)


def dispatch(name: str, action_input: dict[str, Any]) -> str:
    t = REGISTRY.get(name)
    if not t:
        return f"ERROR: unknown tool '{name}'. Available: {', '.join(REGISTRY)}"
    try:
        result = t.run(**(action_input or {}))
        return str(result)
    except TypeError as e:
        return f"ERROR calling {name}: bad arguments ({e})"
    except Exception as e:
        return f"ERROR in {name}: {e}"
