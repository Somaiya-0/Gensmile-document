"""
IP blocklist for suspicious activity -- escalates on top of the existing
per-route rate limits (app.core.rate_limit / slowapi). A rate limit alone
just slows a client down for the current window; this bans an IP outright
for a cooldown period once it shows a pattern of abuse (repeated rate-limit
violations, repeated failed logins), and lets an admin block/unblock an IP
by hand too.

ponytail: in-process memory, not shared across workers or processes, and
reset on restart. Correct for the current single-worker/single-instance
deployment. If this ever runs behind multiple Uvicorn workers or multiple
instances, move _strikes/_blocked_until to Redis (or a DB table) so every
worker sees the same blocklist -- until then that's unneeded complexity.
"""
from __future__ import annotations

import time
from collections import defaultdict

from app.core.config import get_settings

settings = get_settings()

# ip -> timestamps of recent "strikes" (rate-limit violations, failed logins)
_strikes: dict[str, list[float]] = defaultdict(list)
# ip -> unix timestamp the block expires at
_blocked_until: dict[str, float] = {}


def record_strike(ip: str) -> None:
    """Record one suspicious event for this IP. Blocks it once strikes
    within the window reach the threshold."""
    if not ip or ip == "unknown":
        return
    now = time.time()
    window_start = now - settings.ip_block_strike_window_seconds
    recent = [t for t in _strikes[ip] if t >= window_start]
    recent.append(now)

    if len(recent) >= settings.ip_block_strike_threshold:
        _blocked_until[ip] = now + settings.ip_block_duration_seconds
        _strikes.pop(ip, None)
    else:
        _strikes[ip] = recent


def is_blocked(ip: str) -> bool:
    until = _blocked_until.get(ip)
    if until is None:
        return False
    if time.time() >= until:
        del _blocked_until[ip]
        return False
    return True


def block_ip(ip: str, *, duration_seconds: int | None = None) -> None:
    """Manual block, e.g. from the admin panel."""
    _blocked_until[ip] = time.time() + (duration_seconds or settings.ip_block_duration_seconds)
    _strikes.pop(ip, None)


def unblock_ip(ip: str) -> bool:
    return _blocked_until.pop(ip, None) is not None


def list_blocked() -> dict[str, float]:
    """Currently-blocked IPs -> unix timestamp they unblock at. Prunes
    expired entries as a side effect."""
    now = time.time()
    for ip in [ip for ip, until in _blocked_until.items() if until <= now]:
        del _blocked_until[ip]
    return dict(_blocked_until)
