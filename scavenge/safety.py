"""Target-URL admission checks.

The page under inspection is hostile input. A diagnostic that will fetch whatever URL
it is handed, and then navigate a real browser to it, is an SSRF primitive even when it
runs on a developer's laptop.
"""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse

ALLOWED_SCHEMES = frozenset({"http", "https"})


class UnsafeTargetError(Exception):
    """Raised rather than returning None: refusing to fetch is not a missing result."""


def check_target(url: str, *, allow_private: bool = False) -> None:
    """`allow_private` exists so the deterministic fixture server on 127.0.0.1 can be
    inspected by the tests. It is never set from the CLI."""
    parts = urlparse(url)
    if parts.scheme not in ALLOWED_SCHEMES:
        raise UnsafeTargetError(f"scheme {parts.scheme!r} is not fetchable; only http/https")
    host = parts.hostname
    if not host:
        raise UnsafeTargetError("target has no host")
    if allow_private:
        return
    for address in _resolve(host):
        if not address.is_global:
            raise UnsafeTargetError(f"{host} resolves to non-public address {address}")


def _resolve(host: str) -> list[ipaddress.IPv4Address | ipaddress.IPv6Address]:
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror as exc:
        raise UnsafeTargetError(f"{host} does not resolve: {exc}") from exc
    return [ipaddress.ip_address(info[4][0]) for info in infos]
