"""
File tools: list, read, write.

Reads and listings are allowed broadly (so ULTRON can inspect your machine),
but WRITES are sandboxed to data/workspace/ by default — a safety rail so the
assistant can't clobber arbitrary files. Loosen this in write_file if you
trust it fully.
"""
from __future__ import annotations

from pathlib import Path

from ..config import settings
from . import tool


def _resolve(path: str) -> Path:
    p = Path(path).expanduser()
    if not p.is_absolute():
        p = settings.workspace_dir / p
    return p


@tool(
    "list_files",
    "List files and folders at a path (defaults to ULTRON's workspace).",
    {"path": "directory path; '.' means the workspace"},
)
def list_files(path: str = ".") -> str:
    p = _resolve(path)
    if not p.exists():
        return f"Path not found: {p}"
    if p.is_file():
        return f"{p} is a file ({p.stat().st_size} bytes)."
    entries = sorted(p.iterdir(), key=lambda e: (e.is_file(), e.name.lower()))
    if not entries:
        return f"{p} is empty."
    lines = [f"Contents of {p}:"]
    for e in entries[:100]:
        kind = "DIR " if e.is_dir() else "FILE"
        size = "" if e.is_dir() else f" ({e.stat().st_size} b)"
        lines.append(f"  [{kind}] {e.name}{size}")
    return "\n".join(lines)


@tool(
    "read_file",
    "Read the text content of a file.",
    {"path": "path to the file"},
)
def read_file(path: str) -> str:
    p = _resolve(path)
    if not p.exists() or not p.is_file():
        return f"File not found: {p}"
    try:
        text = p.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        return f"Could not read {p}: {e}"
    return f"--- {p} ({len(text)} chars) ---\n{text[:4000]}"


@tool(
    "write_file",
    "Create or overwrite a file inside ULTRON's workspace.",
    {"path": "filename or relative path", "content": "text to write"},
)
def write_file(path: str, content: str) -> str:
    p = _resolve(path)
    # keep writes inside the workspace sandbox
    try:
        p.resolve().relative_to(settings.workspace_dir.resolve())
    except ValueError:
        return (f"Refused: writes are sandboxed to {settings.workspace_dir}. "
                f"Use a path inside the workspace.")
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return f"Wrote {len(content)} chars to {p}."
