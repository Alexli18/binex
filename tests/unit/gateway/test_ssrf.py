"""SSRF protection for fetch_url / http_request (issue #59)."""

from __future__ import annotations

import socket
from unittest.mock import patch

import pytest

from binex.tools.builtins import get_builtin
from binex.tools.ssrf import BlockedURLError, guarded_fetch, validate_url


def _fake_getaddrinfo(host, port=None, *args, **kwargs):
    """Resolve a known public host to a public IP; literal IPs to themselves."""
    ip = {"public.test": "93.184.216.34", "example.com": "93.184.216.34"}.get(host, host)
    return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, port or 0))]


class _FakeResp:
    def __init__(self, status, headers=None, text=""):
        self.status_code = status
        self.headers = headers or {}
        self.text = text

    def raise_for_status(self):
        pass


class _FakeClient:
    def __init__(self, responses):
        self._responses = list(responses)
        self._i = 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        pass

    async def request(self, method, url, **kwargs):
        resp = self._responses[self._i]
        self._i += 1
        return resp


# ── validate_url ─────────────────────────────────────────────────────────

@pytest.mark.parametrize("url", [
    "http://169.254.169.254/latest/meta-data/",  # cloud metadata
    "http://127.0.0.1:8080/admin",               # loopback
    "http://localhost/",                         # loopback by name
    "http://10.0.0.5/internal",                  # RFC 1918
    "http://192.168.1.1/",                       # RFC 1918
    "http://0.0.0.0/",                           # unspecified
    "file:///etc/passwd",                        # non-http scheme
])
def test_validate_url_blocks(url):
    with pytest.raises(BlockedURLError):
        validate_url(url)


def test_validate_url_allows_public():
    with patch("socket.getaddrinfo", _fake_getaddrinfo):
        validate_url("https://example.com/")  # must not raise


def test_dns_rebinding_to_private_blocked():
    """A public-looking hostname that resolves to a private IP is blocked."""
    def _resolve_private(host, port=None, *a, **k):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.1.2.3", 0))]

    with patch("socket.getaddrinfo", _resolve_private):
        with pytest.raises(BlockedURLError):
            validate_url("http://sneaky.example.com/")


def test_opt_out_allows_private(monkeypatch):
    monkeypatch.setenv("BINEX_ALLOW_PRIVATE_URLS", "1")
    validate_url("http://127.0.0.1/")  # must not raise


# ── redirect re-check ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_redirect_to_internal_is_blocked():
    """A public URL that 302s to the metadata service is blocked on the hop."""
    redirect = _FakeResp(302, headers={"location": "http://169.254.169.254/"})
    with patch("socket.getaddrinfo", _fake_getaddrinfo), \
         patch("httpx.AsyncClient", lambda *a, **k: _FakeClient([redirect])):
        with pytest.raises(BlockedURLError):
            await guarded_fetch("GET", "http://public.test/")


@pytest.mark.asyncio
async def test_public_redirect_followed():
    """A redirect to another public URL is followed normally."""
    hop1 = _FakeResp(302, headers={"location": "https://example.com/final"})
    hop2 = _FakeResp(200, text="OK")
    with patch("socket.getaddrinfo", _fake_getaddrinfo), \
         patch("httpx.AsyncClient", lambda *a, **k: _FakeClient([hop1, hop2])):
        resp = await guarded_fetch("GET", "http://public.test/")
    assert resp.status_code == 200 and resp.text == "OK"


# ── tool integration ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_fetch_url_tool_blocks_metadata():
    fetch = get_builtin("fetch_url")
    result = await fetch.callable(url="http://169.254.169.254/latest/meta-data/")
    assert "blocked URL" in result


@pytest.mark.asyncio
async def test_http_request_tool_blocks_localhost():
    http = get_builtin("http_request")
    result = await http.callable(url="http://127.0.0.1:9000/admin", method="GET")
    assert "blocked URL" in result
