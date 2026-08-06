"""Tests for gateway authentication middleware."""

from __future__ import annotations

import pytest

from binex.gateway.auth import (
    ApiKeyAuth,
    AuthResult,
    GatewayAuth,
    NoAuth,
    create_auth,
)
from binex.gateway.config import ApiKeyEntry, AuthConfig

# ── AuthResult model ────────────────────────────────────────────────


class TestAuthResult:
    def test_authenticated_result(self):
        r = AuthResult(authenticated=True, client_name="alice")
        assert r.authenticated is True
        assert r.client_name == "alice"
        assert r.error is None

    def test_unauthenticated_result(self):
        r = AuthResult(authenticated=False, error="bad key")
        assert r.authenticated is False
        assert r.client_name is None
        assert r.error == "bad key"

    def test_defaults(self):
        r = AuthResult(authenticated=True)
        assert r.client_name is None
        assert r.error is None


# ── NoAuth ──────────────────────────────────────────────────────────


class TestNoAuth:
    @pytest.mark.asyncio
    async def test_always_authenticated(self):
        auth = NoAuth()
        result = await auth.authenticate({})
        assert result.authenticated is True

    @pytest.mark.asyncio
    async def test_with_random_headers(self):
        auth = NoAuth()
        result = await auth.authenticate({"Authorization": "Bearer xyz"})
        assert result.authenticated is True

    def test_implements_protocol(self):
        assert isinstance(NoAuth(), GatewayAuth)


# ── ApiKeyAuth ──────────────────────────────────────────────────────


def _make_auth(*keys: tuple[str, str]) -> ApiKeyAuth:
    """Helper to build ApiKeyAuth from (name, key) tuples."""
    entries = [ApiKeyEntry(name=n, key=k) for n, k in keys]
    return ApiKeyAuth(keys=entries)


class TestApiKeyAuth:
    @pytest.mark.asyncio
    async def test_valid_key(self):
        auth = _make_auth(("alice", "secret-1"))
        result = await auth.authenticate({"X-API-Key": "secret-1"})
        assert result.authenticated is True
        assert result.client_name == "alice"
        assert result.error is None

    @pytest.mark.asyncio
    async def test_invalid_key(self):
        auth = _make_auth(("alice", "secret-1"))
        result = await auth.authenticate({"X-API-Key": "wrong"})
        assert result.authenticated is False
        assert result.error == "Invalid or missing API key"
        assert result.client_name is None

    @pytest.mark.asyncio
    async def test_missing_header(self):
        auth = _make_auth(("alice", "secret-1"))
        result = await auth.authenticate({})
        assert result.authenticated is False
        assert result.error == "Invalid or missing API key"

    @pytest.mark.asyncio
    async def test_empty_header(self):
        auth = _make_auth(("alice", "secret-1"))
        result = await auth.authenticate({"X-API-Key": ""})
        assert result.authenticated is False
        assert result.error == "Invalid or missing API key"

    @pytest.mark.asyncio
    async def test_multiple_keys(self):
        auth = _make_auth(("alice", "key-a"), ("bob", "key-b"))
        r1 = await auth.authenticate({"X-API-Key": "key-a"})
        assert r1.authenticated is True
        assert r1.client_name == "alice"

        r2 = await auth.authenticate({"X-API-Key": "key-b"})
        assert r2.authenticated is True
        assert r2.client_name == "bob"

    @pytest.mark.asyncio
    async def test_case_sensitive_key(self):
        auth = _make_auth(("alice", "Secret-1"))
        result = await auth.authenticate({"X-API-Key": "secret-1"})
        assert result.authenticated is False

    @pytest.mark.asyncio
    async def test_case_insensitive_header_name(self):
        """Header lookup should be case-insensitive."""
        auth = _make_auth(("alice", "key-a"))
        result = await auth.authenticate({"x-api-key": "key-a"})
        assert result.authenticated is True
        assert result.client_name == "alice"

    @pytest.mark.asyncio
    async def test_header_name_mixed_case(self):
        auth = _make_auth(("alice", "key-a"))
        result = await auth.authenticate({"X-Api-Key": "key-a"})
        assert result.authenticated is True

    def test_implements_protocol(self):
        auth = _make_auth(("a", "b"))
        assert isinstance(auth, GatewayAuth)


# ── create_auth factory ─────────────────────────────────────────────


class TestCreateAuth:
    def test_none_config_returns_noauth(self):
        auth = create_auth(None)
        assert isinstance(auth, NoAuth)

    def test_config_returns_apikey_auth(self):
        config = AuthConfig(
            type="api_key",
            keys=[ApiKeyEntry(name="test", key="k1")],
        )
        auth = create_auth(config)
        assert isinstance(auth, ApiKeyAuth)

    @pytest.mark.asyncio
    async def test_factory_apikey_works(self):
        config = AuthConfig(
            type="api_key",
            keys=[ApiKeyEntry(name="svc", key="tok-123")],
        )
        auth = create_auth(config)
        r = await auth.authenticate({"X-API-Key": "tok-123"})
        assert r.authenticated is True
        assert r.client_name == "svc"
