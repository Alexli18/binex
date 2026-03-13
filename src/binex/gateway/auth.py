"""Gateway authentication middleware."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from pydantic import BaseModel

from binex.gateway.config import ApiKeyEntry, AuthConfig


class AuthResult(BaseModel):
    """Result of an authentication attempt."""

    authenticated: bool
    client_name: str | None = None
    error: str | None = None


@runtime_checkable
class GatewayAuth(Protocol):
    """Protocol for gateway authentication backends."""

    async def authenticate(self, request_headers: dict) -> AuthResult: ...


class NoAuth:
    """No-op authenticator — allows all requests."""

    async def authenticate(self, request_headers: dict) -> AuthResult:
        return AuthResult(authenticated=True)


class ApiKeyAuth:
    """Authenticator that validates X-API-Key header against a key list."""

    def __init__(self, keys: list[ApiKeyEntry]) -> None:
        # Build lookup: key_value -> client name
        self._keys: dict[str, str] = {entry.key: entry.name for entry in keys}

    async def authenticate(self, request_headers: dict) -> AuthResult:
        # Case-insensitive header lookup
        normalized = {k.lower(): v for k, v in request_headers.items()}
        api_key = normalized.get("x-api-key", "")

        client_name = self._keys.get(api_key)
        if client_name is not None:
            return AuthResult(authenticated=True, client_name=client_name)

        return AuthResult(
            authenticated=False,
            error="Invalid or missing API key",
        )


def create_auth(config: AuthConfig | None) -> GatewayAuth:
    """Factory: build the appropriate auth backend from config."""
    if config is None:
        return NoAuth()
    return ApiKeyAuth(keys=config.keys)
