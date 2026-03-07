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
        self.default_backoff: Literal["fixed", "exponential"] = os.environ.get(  # type: ignore[assignment]
            "BINEX_DEFAULT_BACKOFF", "exponential"
        )

    @property
    def artifacts_dir(self) -> str:
        return f"{self.store_path}/artifacts"

    @property
    def db_path(self) -> str:
        return f"{self.store_path}/binex.db"


__all__ = ["Settings"]
