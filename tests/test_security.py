from __future__ import annotations

import time

from src.services.security import RequestThrottle, clean_user_input


def test_sanitize_text_strips_control_chars():
    dirty = "Hello\x00World\x07\n\t!"
    cleaned = clean_user_input(dirty)
    assert cleaned == "HelloWorld !"


def test_sanitize_text_collapses_whitespace():
    assert clean_user_input("   too   much    space   ") == "too much space"


def test_sanitize_text_truncates():
    long_text = "x" * 300
    assert len(clean_user_input(long_text)) == 280


def test_rate_limiter_consumes_and_refills():
    throttle = RequestThrottle(capacity=2, refill_per_sec=10.0)

    # First two requests pass instantly
    allowed, retry = throttle.check("ip1")
    assert allowed is True
    assert retry == 0.0

    allowed, retry = throttle.check("ip1")
    assert allowed is True

    # Third request is blocked (bucket empty)
    allowed, retry = throttle.check("ip1")
    assert allowed is False
    assert retry > 0.0

    # Wait for refill
    time.sleep(0.15)
    allowed, retry = throttle.check("ip1")
    assert allowed is True


def test_rate_limiter_isolates_clients():
    throttle = RequestThrottle(capacity=1, refill_per_sec=0.0)
    assert throttle.check("ip1")[0] is True
    assert throttle.check("ip1")[0] is False  # ip1 blocked

    # ip2 has its own bucket
    assert throttle.check("ip2")[0] is True


def test_rate_limiter_evicts_idle_buckets():
    throttle = RequestThrottle(capacity=1, refill_per_sec=0.0, max_entries=2)
    throttle.check("ip1")
    time.sleep(0.01)
    throttle.check("ip2")
    time.sleep(0.01)
    throttle.check("ip3")  # Causes eviction of the oldest (ip1)

    with throttle._lock:
        assert "ip1" not in throttle._buckets
        assert "ip2" in throttle._buckets
        assert "ip3" in throttle._buckets
