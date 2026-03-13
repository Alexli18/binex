"""Gateway configuration models and YAML loader."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field, field_validator, model_validator


class ApiKeyEntry(BaseModel):
    """A single API key credential."""

    name: str
    key: str

    @field_validator("key")
    @classmethod
    def key_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("API key must not be empty")
        return v


class AuthConfig(BaseModel):
    """Authentication settings."""

    type: Literal["api_key"] = "api_key"
    keys: list[ApiKeyEntry] = Field(default_factory=list)

    @field_validator("type")
    @classmethod
    def supported_type(cls, v: str) -> str:
        if v not in ("api_key",):
            raise ValueError(
                f"Unknown auth type '{v}'. Supported types: api_key"
            )
        return v


class AgentEntry(BaseModel):
    """A registered remote agent."""

    name: str
    endpoint: str
    capabilities: list[str] = Field(default_factory=list)
    priority: int = 0


class FallbackConfig(BaseModel):
    """Retry and failover behavior."""

    retry_count: int = 2
    retry_backoff: Literal["fixed", "exponential"] = "exponential"
    retry_base_delay_ms: int = 500
    failover: bool = True

    @field_validator("retry_count")
    @classmethod
    def retry_count_non_negative(cls, v: int) -> int:
        if v < 0:
            raise ValueError("retry_count must be >= 0")
        return v

    @field_validator("retry_base_delay_ms")
    @classmethod
    def base_delay_positive(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("retry_base_delay_ms must be > 0")
        return v


class HealthConfig(BaseModel):
    """Background health checking parameters."""

    interval_s: int = 30
    timeout_ms: int = 5000

    @field_validator("interval_s")
    @classmethod
    def interval_positive(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("interval_s must be > 0")
        return v

    @field_validator("timeout_ms")
    @classmethod
    def timeout_positive(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("timeout_ms must be > 0")
        return v


class GatewayConfig(BaseModel):
    """Central gateway configuration loaded from gateway.yaml."""

    host: str = "0.0.0.0"
    port: int = 8420
    auth: AuthConfig | None = None
    agents: list[AgentEntry] = Field(default_factory=list)
    fallback: FallbackConfig = Field(default_factory=FallbackConfig)
    health: HealthConfig = Field(default_factory=HealthConfig)

    @model_validator(mode="after")
    def _validate_config(self) -> GatewayConfig:
        # Duplicate agent names
        names = [a.name for a in self.agents]
        if len(names) != len(set(names)):
            dupes = {n for n in names if names.count(n) > 1}
            raise ValueError(f"Duplicate agent names: {dupes}")
        # Auth requires at least one key
        if self.auth is not None and len(self.auth.keys) == 0:
            raise ValueError(
                "Auth is configured but no API keys provided"
            )
        return self


# ── ENV interpolation ───────────────────────────────────────────────

_ENV_PATTERN = re.compile(r"\$\{(\w+)\}")


def _interpolate_env(value: str) -> str:
    """Replace ${VAR} references with environment variable values."""
    def _replace(match: re.Match) -> str:
        var_name = match.group(1)
        val = os.environ.get(var_name)
        if val is None:
            raise ValueError(
                f"Environment variable '{var_name}' is not set "
                f"(referenced as ${{{var_name}}} in gateway config)"
            )
        return val
    return _ENV_PATTERN.sub(_replace, value)


def _interpolate_recursive(obj: object) -> object:
    """Recursively interpolate env vars in a parsed YAML structure."""
    if isinstance(obj, str):
        return _interpolate_env(obj)
    if isinstance(obj, dict):
        return {k: _interpolate_recursive(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_interpolate_recursive(item) for item in obj]
    return obj


# ── Config search ───────────────────────────────────────────────────

def _search_config_paths() -> list[str]:
    """Return candidate config file paths in priority order."""
    cwd = Path.cwd()
    return [
        str(cwd / ".binex" / "gateway.yaml"),
        str(cwd / "gateway.yaml"),
    ]


def load_gateway_config(path: str | None) -> GatewayConfig | None:
    """Load gateway config from YAML.

    Search order: explicit path → .binex/gateway.yaml → ./gateway.yaml → None.
    """
    if path is not None:
        config_path = Path(path)
        if not config_path.exists():
            return None
        candidates = [str(config_path)]
    else:
        candidates = _search_config_paths()

    for candidate in candidates:
        p = Path(candidate)
        if p.exists():
            raw = yaml.safe_load(p.read_text())
            if raw is None:
                raw = {}
            interpolated = _interpolate_recursive(raw)
            return GatewayConfig(**interpolated)

    return None
