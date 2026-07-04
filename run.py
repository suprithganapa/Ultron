#!/usr/bin/env python3
"""
ULTRON launcher.

    python run.py

Boots the FastAPI server and serves the dashboard. Open the printed URL
in your browser and talk to ULTRON by voice or text.
"""
import uvicorn

from backend.config import settings

if __name__ == "__main__":
    print("\n  Booting ULTRON...\n")
    uvicorn.run(
        "backend.main:app",
        host=settings.host,
        port=settings.port,
        reload=False,
    )
