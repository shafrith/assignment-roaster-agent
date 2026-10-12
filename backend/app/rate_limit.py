"""Shared slowapi rate limiter.

Unauthenticated routes are keyed by client IP (:func:`client_ip`). Authenticated routes use
:func:`user_or_ip_key`, which keys by the access token's user id so users behind one NAT or
proxy don't share a bucket, and rotating IPs doesn't buy a fresh one.

Proxy awareness: the client IP is ``request.client.host`` and nothing here reads
``X-Forwarded-For``. Behind a reverse proxy, run uvicorn with ``--proxy-headers
--forwarded-allow-ips=<proxy IP/CIDR>`` so uvicorn (and only uvicorn) rewrites the client
address from headers sent by that trusted proxy. Never use ``--forwarded-allow-ips='*'``
when clients can reach uvicorn directly: they could spoof the header.

Usage in routers::

    from app.rate_limit import limiter, user_or_ip_key

    @router.post("/thing")
    @limiter.limit("10/minute", key_func=user_or_ip_key)
    async def thing(request: Request) -> ...:
        ...

The decorated endpoint must accept a ``request: Request`` parameter.
"""

from slowapi import Limiter
from starlette.requests import Request

from app.auth.jwt import decode_access_token
from app.config import settings
from app.exceptions import UnauthorizedError

_BEARER_PREFIX = "bearer "


def client_ip(request: Request) -> str:
    """Return the client IP as resolved by uvicorn (proxy headers only from trusted proxies).

    Args:
        request: Incoming request.

    Returns:
        ``"ip:<address>"``, or ``"ip:unknown"`` when the transport gives no address.
    """
    host = request.client.host if request.client else None
    return f"ip:{host or 'unknown'}"


def user_or_ip_key(request: Request) -> str:
    """Key by the authenticated user id when a valid access token is present, else by IP.

    The token signature and expiry are verified, so a forged ``sub`` cannot borrow or exhaust
    another user's bucket.

    Args:
        request: Incoming request.

    Returns:
        ``"user:<id>"`` or the :func:`client_ip` key.
    """
    authorization = request.headers.get("authorization", "")
    if authorization.lower().startswith(_BEARER_PREFIX):
        token = authorization[len(_BEARER_PREFIX) :].strip()
        if token:
            try:
                return f"user:{decode_access_token(token)}"
            except UnauthorizedError:
                pass
    return client_ip(request)


limiter: Limiter = Limiter(
    key_func=client_ip,
    enabled=settings.ENVIRONMENT != "test",
)
