"""SSRF protection for the HTTP built-in tools.

``fetch_url`` / ``http_request`` fetch whatever URL the model produces. On a
laptop that's low risk, but Binex also ships a gateway and a cron scheduler that
run on servers — where an LLM-controlled HTTP client can reach cloud metadata
endpoints (169.254.169.254), localhost admin panels, and internal services.

This module resolves a URL's host and rejects private/loopback/link-local
addresses before connecting, and re-checks on every redirect hop. See issue #59.
"""

from __future__ import annotations

import ipaddress
import os
import socket
from typing import Any
from urllib.parse import urljoin, urlparse

MAX_REDIRECTS = 5


class BlockedURLError(Exception):
    """Raised when a URL is disallowed by the SSRF policy."""


def _ip_is_blocked(ip: str) -> bool:
    """True for private/loopback/link-local/reserved/multicast addresses."""
    addr = ipaddress.ip_address(ip)
    return (
        addr.is_private        # RFC 1918 (10/8, 172.16/12, 192.168/16), fc00::/7
        or addr.is_loopback    # 127.0.0.0/8, ::1
        or addr.is_link_local  # 169.254.0.0/16 (cloud metadata), fe80::/10
        or addr.is_reserved
        or addr.is_multicast
        or addr.is_unspecified  # 0.0.0.0, ::
    )


def validate_url(url: str) -> None:
    """Raise BlockedURLError if the URL targets a non-public address.

    Skipped when ``BINEX_ALLOW_PRIVATE_URLS=1`` (opt-in for legitimate local use).
    """
    if os.environ.get("BINEX_ALLOW_PRIVATE_URLS") == "1":
        return

    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise BlockedURLError(f"URL scheme '{parsed.scheme}' is not allowed")
    host = parsed.hostname
    if not host:
        raise BlockedURLError("URL has no host")

    try:
        infos = socket.getaddrinfo(host, parsed.port or None)
    except socket.gaierror as exc:
        raise BlockedURLError(f"cannot resolve host '{host}': {exc}") from exc

    for info in infos:
        ip = str(info[4][0])
        if _ip_is_blocked(ip):
            raise BlockedURLError(
                f"host '{host}' resolves to blocked address {ip} "
                f"(private/loopback/link-local). Set BINEX_ALLOW_PRIVATE_URLS=1 "
                f"to allow local requests."
            )


async def guarded_fetch(
    method: str,
    url: str,
    *,
    content: str | None = None,
    headers: dict[str, str] | None = None,
    timeout: float = 30,
    max_redirects: int = MAX_REDIRECTS,
) -> Any:
    """Perform an HTTP request, validating the address on every redirect hop.

    Redirects are followed manually (httpx auto-redirects are disabled) so each
    hop's destination is re-validated — a public URL can't 302 into the metadata
    service.
    """
    import httpx

    async with httpx.AsyncClient(timeout=timeout, follow_redirects=False) as client:
        current = url
        current_method = method
        current_content = content
        for _ in range(max_redirects + 1):
            validate_url(current)
            resp = await client.request(
                current_method, current,
                content=current_content if current_content else None,
                headers=headers,
            )
            if resp.status_code in (301, 302, 303, 307, 308):
                location = resp.headers.get("location")
                if not location:
                    return resp
                current = urljoin(current, location)
                # 303 (and commonly 301/302) redirect to GET without a body.
                if resp.status_code in (301, 302, 303):
                    current_method = "GET"
                    current_content = None
                continue
            return resp
    raise BlockedURLError(f"too many redirects (>{max_redirects})")
