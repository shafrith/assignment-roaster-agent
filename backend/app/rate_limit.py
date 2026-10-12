"""Shared slowapi rate limiter, keyed by client IP (:func:`client_ip`).

Proxy awareness: the client IP is ``request.client.host`` and nothing here reads
``X-Forwarded-For``. Behind a reverse proxy, run uvicorn with ``--proxy-headers
--forwarded-allow-ips=<proxy IP/CIDR>`` so uvicorn (and only uvicorn) rewrites the client
address from headers sent by that trusted proxy. Never use ``--forwarded-allow-ips='*'``
when clients can reach uvicorn directly: they could spoof the header.

Usage in routers::

    from app.rate_limit import limiter

    @router.post("/thing")
    @limiter.limit("10/minute")
    async def thing(request: Request) -> ...:
        ...

The decorated endpoint must accept a ``request: Request`` parameter.
"""

import hashlib
import hmac

from slowapi import Limiter
from starlette.requests import Request

from app.config import settings


def client_ip(request: Request) -> str:
    """Return the client IP as resolved by uvicorn (proxy headers only from trusted proxies).

    Args:
        request: Incoming request.

    Returns:
        ``"ip:<address>"``, or ``"ip:unknown"`` when the transport gives no address.
    """
    host = request.client.host if request.client else None
    return f"ip:{host or 'unknown'}"


def client_quota_key(request: Request) -> str:
    """Return a stable, non-reversible daily-quota key for the caller.

    The key is an HMAC-SHA256 (keyed with ``SECRET_KEY``) of :func:`client_ip`, so the daily
    quota can be enforced per client without storing raw IP addresses.

    Args:
        request: Incoming request.

    Returns:
        64-character hex digest.
    """
    return hmac.new(
        settings.SECRET_KEY.encode(), client_ip(request).encode(), hashlib.sha256
    ).hexdigest()


limiter: Limiter = Limiter(
    key_func=client_ip,
    enabled=settings.ENVIRONMENT != "test",
)
