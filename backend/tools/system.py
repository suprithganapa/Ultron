"""System tools: time and machine info."""
from __future__ import annotations

import platform
import shutil
import time
from datetime import datetime

from . import tool


@tool("get_time", "Get the current date and time.", {})
def get_time() -> str:
    now = datetime.now()
    return now.strftime("It is %A, %d %B %Y, %I:%M:%S %p (local time).")


@tool("system_info", "Report information about the host machine.", {})
def system_info() -> str:
    total, used, free = shutil.disk_usage("/")
    gb = 1024 ** 3
    return (
        f"System diagnostics, sir:\n"
        f"- OS: {platform.system()} {platform.release()}\n"
        f"- Machine: {platform.machine()}\n"
        f"- Processor: {platform.processor() or 'n/a'}\n"
        f"- Python: {platform.python_version()}\n"
        f"- Disk: {used // gb} GB used / {total // gb} GB total "
        f"({free // gb} GB free)\n"
        f"- Uptime marker: {time.strftime('%X')}"
    )
