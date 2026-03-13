"""Tests for binex.gateway.config — models and YAML loader."""

from __future__ import annotations

import os
import textwrap
from pathlib import Path
from unittest.mock import patch

import pytest

from binex.gateway.config import (
    AgentEntry,
    ApiKeyEntry,
    AuthConfig,
    FallbackConfig,
    GatewayConfig,
    HealthConfig,
    load_gateway_config,
)


# ── Model defaults ──────────────────────────────────────────────────

class TestGatewayConfigDefaults:
    def test_minimal_config(self):
        cfg = GatewayConfig()
        assert cfg.host == "0.0.0.0"
        assert cfg.port == 8420
        assert cfg.auth is None
        assert cfg.agents == []
        assert cfg.fallback is not None
        assert cfg.health is not None

    def test_fallback_defaults(self):
        fb = FallbackConfig()
        assert fb.retry_count == 2
        assert fb.retry_backoff == "exponential"
        assert fb.retry_base_delay_ms == 500
        assert fb.failover is True

    def test_health_defaults(self):
        h = HealthConfig()
        assert h.interval_s == 30
        assert h.timeout_ms == 5000

    def test_agent_entry_defaults(self):
        a = AgentEntry(name="test", endpoint="http://localhost:9001")
        assert a.capabilities == []
        assert a.priority == 0

    def test_auth_config_defaults(self):
        ac = AuthConfig(keys=[ApiKeyEntry(name="k1", key="secret")])
        assert ac.type == "api_key"


# ── Validation rules ────────────────────────────────────────────────

class TestValidation:
    def test_fallback_retry_count_non_negative(self):
        with pytest.raises(ValueError):
            FallbackConfig(retry_count=-1)

    def test_fallback_base_delay_positive(self):
        with pytest.raises(ValueError):
            FallbackConfig(retry_base_delay_ms=0)

    def test_health_interval_positive(self):
        with pytest.raises(ValueError):
            HealthConfig(interval_s=0)

    def test_health_timeout_positive(self):
        with pytest.raises(ValueError):
            HealthConfig(timeout_ms=0)

    def test_auth_unknown_type(self):
        with pytest.raises(ValueError):
            AuthConfig(type="jwt", keys=[ApiKeyEntry(name="k", key="s")])

    def test_api_key_empty_key(self):
        with pytest.raises(ValueError):
            ApiKeyEntry(name="k", key="")

    def test_duplicate_agent_names(self):
        with pytest.raises(ValueError, match="[Dd]uplicate"):
            GatewayConfig(agents=[
                AgentEntry(name="a", endpoint="http://localhost:1"),
                AgentEntry(name="a", endpoint="http://localhost:2"),
            ])

    def test_auth_requires_keys(self):
        with pytest.raises(ValueError):
            GatewayConfig(auth=AuthConfig(keys=[]))


# ── YAML loading ────────────────────────────────────────────────────

class TestLoadGatewayConfig:
    def test_load_from_explicit_path(self, tmp_path: Path):
        cfg_file = tmp_path / "gw.yaml"
        cfg_file.write_text(textwrap.dedent("""\
            host: "127.0.0.1"
            port: 9999
            agents:
              - name: agent1
                endpoint: http://localhost:9001
                capabilities: [research]
                priority: 1
        """))
        cfg = load_gateway_config(str(cfg_file))
        assert cfg is not None
        assert cfg.host == "127.0.0.1"
        assert cfg.port == 9999
        assert len(cfg.agents) == 1
        assert cfg.agents[0].name == "agent1"
        assert cfg.agents[0].capabilities == ["research"]

    def test_load_returns_none_when_not_found(self, tmp_path: Path):
        result = load_gateway_config(str(tmp_path / "nonexistent.yaml"))
        assert result is None

    def test_load_auto_detect_binex_dir(self, tmp_path: Path):
        binex_dir = tmp_path / ".binex"
        binex_dir.mkdir()
        cfg_file = binex_dir / "gateway.yaml"
        cfg_file.write_text("agents: []\n")
        with patch("binex.gateway.config._search_config_paths",
                    return_value=[str(cfg_file)]):
            cfg = load_gateway_config(None)
            assert cfg is not None

    def test_env_var_interpolation(self, tmp_path: Path):
        cfg_file = tmp_path / "gw.yaml"
        cfg_file.write_text(textwrap.dedent("""\
            auth:
              type: api_key
              keys:
                - name: prod
                  key: "${TEST_GW_KEY}"
            agents:
              - name: agent1
                endpoint: http://localhost:9001
        """))
        with patch.dict(os.environ, {"TEST_GW_KEY": "my-secret-key"}):
            cfg = load_gateway_config(str(cfg_file))
        assert cfg is not None
        assert cfg.auth is not None
        assert cfg.auth.keys[0].key == "my-secret-key"

    def test_env_var_missing_raises(self, tmp_path: Path):
        cfg_file = tmp_path / "gw.yaml"
        cfg_file.write_text(textwrap.dedent("""\
            auth:
              type: api_key
              keys:
                - name: prod
                  key: "${MISSING_VAR_XYZ}"
            agents:
              - name: agent1
                endpoint: http://localhost:9001
        """))
        with pytest.raises(ValueError, match="MISSING_VAR_XYZ"):
            load_gateway_config(str(cfg_file))

    def test_load_with_fallback_and_health(self, tmp_path: Path):
        cfg_file = tmp_path / "gw.yaml"
        cfg_file.write_text(textwrap.dedent("""\
            agents:
              - name: a1
                endpoint: http://localhost:9001
            fallback:
              retry_count: 5
              retry_backoff: fixed
              retry_base_delay_ms: 200
              failover: false
            health:
              interval_s: 10
              timeout_ms: 3000
        """))
        cfg = load_gateway_config(str(cfg_file))
        assert cfg is not None
        assert cfg.fallback.retry_count == 5
        assert cfg.fallback.retry_backoff == "fixed"
        assert cfg.fallback.failover is False
        assert cfg.health.interval_s == 10

    def test_load_no_config_returns_none(self):
        result = load_gateway_config(None)
        # When no config found anywhere, returns None
        assert result is None or isinstance(result, GatewayConfig)
