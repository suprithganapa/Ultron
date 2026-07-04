"""
Execution tools: run a shell command, run Python code.

Both are gated by safety switches in .env (ALLOW_SHELL / ALLOW_CODE_EXEC)
and run with a timeout inside the workspace directory.
"""
from __future__ import annotations

import subprocess
import sys
import tempfile

from ..config import settings
from . import tool


@tool(
    "run_shell",
    "Run a shell command and return its output. Use for quick system actions.",
    {"command": "the shell command to execute"},
)
def run_shell(command: str) -> str:
    if not settings.allow_shell:
        return "Shell execution is disabled (set ALLOW_SHELL=true in .env)."
    try:
        proc = subprocess.run(
            command, shell=True, capture_output=True, text=True,
            timeout=30, cwd=settings.workspace_dir,
        )
    except subprocess.TimeoutExpired:
        return "Command timed out after 30s."
    out = (proc.stdout or "") + (proc.stderr or "")
    out = out.strip() or "(no output)"
    return f"[exit {proc.returncode}]\n{out[:3000]}"


@tool(
    "run_python",
    "Execute a snippet of Python code and return stdout / result.",
    {"code": "the Python source to run"},
)
def run_python(code: str) -> str:
    if not settings.allow_code_exec:
        return "Code execution is disabled (set ALLOW_CODE_EXEC=true in .env)."
    with tempfile.NamedTemporaryFile(
        "w", suffix=".py", delete=False, dir=settings.workspace_dir, encoding="utf-8"
    ) as f:
        f.write(code)
        path = f.name
    try:
        proc = subprocess.run(
            [sys.executable, path], capture_output=True, text=True,
            timeout=30, cwd=settings.workspace_dir,
        )
    except subprocess.TimeoutExpired:
        return "Python execution timed out after 30s."
    out = (proc.stdout or "") + (proc.stderr or "")
    return f"[exit {proc.returncode}]\n{out.strip()[:3000] or '(no output)'}"
