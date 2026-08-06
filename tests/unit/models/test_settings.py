"""Tests for Binex application settings."""

from __future__ import annotations

import os
from unittest.mock import patch

from binex.settings import Settings


class TestSettings:
    def test_default_values(self) -> None:
        s = Settings()
        assert s.store_path == ".binex"
        assert s.default_deadline_ms == 120000
        assert s.registry_url == "http://localhost:8000"
        assert s.default_max_retries == 1
        assert s.default_backoff == "exponential"

    def test_env_override(self) -> None:
        env = {
            "BINEX_STORE_PATH": "/tmp/custom",
            "BINEX_DEFAULT_DEADLINE_MS": "60000",
            "BINEX_REGISTRY_URL": "http://registry:9000",
            "BINEX_DEFAULT_MAX_RETRIES": "3",
            "BINEX_DEFAULT_BACKOFF": "fixed",
        }
        with patch.dict(os.environ, env, clear=False):
            s = Settings()
            assert s.store_path == "/tmp/custom"
            assert s.default_deadline_ms == 60000
            assert s.registry_url == "http://registry:9000"
            assert s.default_max_retries == 3
            assert s.default_backoff == "fixed"

    def test_artifacts_dir(self) -> None:
        s = Settings()
        assert s.artifacts_dir == ".binex/artifacts"

    def test_db_path(self) -> None:
        s = Settings()
        assert s.db_path == ".binex/binex.db"
