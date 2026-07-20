"""Application settings for Binex, configurable via environment variables."""

from __future__ import annotations

import os
from typing import Literal


class Settings:
    """Binex runtime settings, configurable via BINEX_* env vars."""

    def __init__(self) -> None:
        self.store_path: str = os.environ.get("BINEX_STORE_PATH", ".binex")
        self.default_deadline_ms: int = int(
            os.environ.get("BINEX_DEFAULT_DEADLINE_MS", "120000")
        )
        self.registry_url: str = os.environ.get(
            "BINEX_REGISTRY_URL", "http://localhost:8000"
        )
        self.default_max_retries: int = int(
            os.environ.get("BINEX_DEFAULT_MAX_RETRIES", "1")
        )
        self.max_concurrency: int = int(
            os.environ.get("BINEX_MAX_CONCURRENCY", "8")
        )
        self.default_backoff: Literal["fixed", "exponential"] = os.environ.get(  # type: ignore[assignment]
            "BINEX_DEFAULT_BACKOFF", "exponential"
        )
        self.cao_server_url: str = os.environ.get(
            "BINEX_CAO_SERVER_URL", "http://localhost:9889"
        )
        self.cao_agent_store_dir: str = os.environ.get(
            "BINEX_CAO_AGENT_STORE",
            self._detect_cao_agent_dir(),
        )

    @staticmethod
    def _detect_cao_agent_dir() -> str:
        """Auto-detect CAO agent profile directory.

        CAO uses ``agent-context`` in newer versions, ``agent-store``
        in older ones.  Return whichever exists, preferring the newer path.
        """
        base = os.path.expanduser("~/.aws/cli-agent-orchestrator")
        for name in ("agent-context", "agent-store"):
            candidate = os.path.join(base, name)
            if os.path.isdir(candidate):
                return candidate
        return os.path.join(base, "agent-store")  # fallback

    @property
    def artifacts_dir(self) -> str:
        return f"{self.store_path}/artifacts"

    @property
    def db_path(self) -> str:
        return f"{self.store_path}/binex.db"


__all__ = ["Settings"]
