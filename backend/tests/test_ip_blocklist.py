"""Tests for app.core.ip_blocklist -- strike counting, auto-block, expiry."""
import time

from app.core import ip_blocklist


def _reset():
    ip_blocklist._strikes.clear()
    ip_blocklist._blocked_until.clear()


def test_strikes_below_threshold_do_not_block():
    _reset()
    for _ in range(ip_blocklist.settings.ip_block_strike_threshold - 1):
        ip_blocklist.record_strike("1.2.3.4")
    assert not ip_blocklist.is_blocked("1.2.3.4")


def test_strikes_at_threshold_block():
    _reset()
    for _ in range(ip_blocklist.settings.ip_block_strike_threshold):
        ip_blocklist.record_strike("1.2.3.4")
    assert ip_blocklist.is_blocked("1.2.3.4")


def test_unrelated_ip_unaffected():
    _reset()
    for _ in range(ip_blocklist.settings.ip_block_strike_threshold):
        ip_blocklist.record_strike("1.2.3.4")
    assert not ip_blocklist.is_blocked("5.6.7.8")


def test_strikes_outside_window_do_not_accumulate():
    _reset()
    now = time.time()
    old = now - ip_blocklist.settings.ip_block_strike_window_seconds - 10
    ip_blocklist._strikes["1.2.3.4"] = [old] * (ip_blocklist.settings.ip_block_strike_threshold - 1)
    ip_blocklist.record_strike("1.2.3.4")  # only this one is within the window
    assert not ip_blocklist.is_blocked("1.2.3.4")


def test_manual_block_and_unblock():
    _reset()
    ip_blocklist.block_ip("9.9.9.9", duration_seconds=60)
    assert ip_blocklist.is_blocked("9.9.9.9")
    assert ip_blocklist.unblock_ip("9.9.9.9")
    assert not ip_blocklist.is_blocked("9.9.9.9")


def test_expired_block_auto_clears():
    _reset()
    ip_blocklist._blocked_until["8.8.8.8"] = time.time() - 1  # already expired
    assert not ip_blocklist.is_blocked("8.8.8.8")
    assert "8.8.8.8" not in ip_blocklist._blocked_until


def test_list_blocked_prunes_expired():
    _reset()
    ip_blocklist._blocked_until["expired.ip"] = time.time() - 1
    ip_blocklist.block_ip("active.ip", duration_seconds=60)
    blocked = ip_blocklist.list_blocked()
    assert "expired.ip" not in blocked
    assert "active.ip" in blocked
