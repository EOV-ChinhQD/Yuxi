"""IP-level rate limiting for failed logins.

Account-level locking (``User.login_failed_count``) only accumulates failures
per account; knowing a username lets an attacker repeatedly lock it out using a
wrong password. This module keeps a sliding-window failure counter over Redis at
two dimensions: ``IP + account`` and ``IP global``, layered on top of
account-level locking. Counters are shared across workers and survive restarts.
An in-memory per-IP throttling layer in middleware remains as a fast first line
of defense.

Trust boundary: the client IP prefers the first ``X-Forwarded-For`` segment
(consistent with access logs). In production, a reverse proxy must overwrite or
strip the client-supplied XFF header, otherwise an attacker can spoof it to
bypass the limit.
"""

from __future__ import annotations

import hashlib
import time
from uuid import uuid4

from yuxi.storage.redis import get_async_redis_client

# Sliding window and thresholds: 10 failures for a single IP+account pair,
# 30 failures IP-wide (within a 10 minute window). The pair threshold sits above
# the account lock threshold (5), so legitimate users hit the account lock
# message first rather than the IP rate limit.
LOGIN_FAILURE_WINDOW_SECONDS = 600
LOGIN_FAILURE_IP_ACCOUNT_MAX = 10
LOGIN_FAILURE_IP_MAX = 30

_IP_KEY_PREFIX = "yuxi:login-failure:ip:"
_IP_ACCOUNT_KEY_PREFIX = "yuxi:login-failure:ipacct:"


def _ip_key(ip: str) -> str:
    return f"{_IP_KEY_PREFIX}{ip}"


def _ip_account_key(ip: str, identifier: str) -> str:
    digest = hashlib.sha1(f"{ip}|{identifier}".encode()).hexdigest()
    return f"{_IP_ACCOUNT_KEY_PREFIX}{digest}"


def extract_client_ip(request) -> str:
    """Extract the client IP, preferring the first X-Forwarded-For segment (matching access logs)."""
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "unknown"


async def check_login_rate_limit(ip: str, identifier: str) -> tuple[bool, int]:
    """Check whether login is rate limited.

    Returns ``(allowed, retry_after_seconds)``; when limited, ``retry_after`` is
    the number of seconds to wait.
    """
    redis = await get_async_redis_client()
    now = time.time()
    window = LOGIN_FAILURE_WINDOW_SECONDS
    limits = (
        (_ip_account_key(ip, identifier), LOGIN_FAILURE_IP_ACCOUNT_MAX),
        (_ip_key(ip), LOGIN_FAILURE_IP_MAX),
    )
    for key, max_failures in limits:
        await redis.zremrangebyscore(key, 0, now - window)
        if await redis.zcard(key) < max_failures:
            continue
        oldest = await redis.zrange(key, 0, 0, withscores=True)
        if not oldest:
            continue
        retry_after = int(oldest[0][1] + window - now) + 1
        return False, max(1, min(window, retry_after))
    return True, 0


async def record_login_failure(ip: str, identifier: str) -> None:
    """Record a login failure in both sliding-window dimensions."""
    redis = await get_async_redis_client()
    now = time.time()
    window = LOGIN_FAILURE_WINDOW_SECONDS
    member = f"{now}-{uuid4().hex[:8]}"
    for key in (_ip_account_key(ip, identifier), _ip_key(ip)):
        await redis.zremrangebyscore(key, 0, now - window)
        await redis.zadd(key, {member: now})
        await redis.expire(key, window)


async def clear_login_failures(ip: str, identifier: str) -> None:
    """Clear the IP+account failure counter on successful login; keep other accounts' IP records."""
    redis = await get_async_redis_client()
    await redis.delete(_ip_account_key(ip, identifier))
