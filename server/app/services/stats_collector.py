"""
In-memory statistics collector for the /api/stats endpoint.

Thread-safe counters that track:
- total_requests
- total_errors (4xx + 5xx responses)
- response times (for avg calculation)

All data is reset when the process restarts — suitable for demo /
judges' evaluation, not for persistent analytics.
"""

import threading
import time
from dataclasses import dataclass, field


@dataclass
class _Stats:
    total_requests: int = 0
    total_errors: int = 0
    response_times: list[float] = field(default_factory=list)
    _lock: threading.Lock = field(
        default_factory=threading.Lock, repr=False, compare=False
    )


_store = _Stats()


def record_request(duration_ms: float, is_error: bool) -> None:
    """
    Record one completed HTTP request.

    Args:
        duration_ms: Wall-clock time for the request in milliseconds.
        is_error:    True if the response status was >= 400.
    """
    with _store._lock:
        _store.total_requests += 1
        _store.response_times.append(duration_ms)
        if is_error:
            _store.total_errors += 1


def get_snapshot() -> dict:
    """
    Return a point-in-time snapshot of all counters.

    Returns a dict with:
        total_requests, total_errors, avg_response_time_ms,
        min_response_time_ms, max_response_time_ms, uptime_info
    """
    with _store._lock:
        # Copy under the lock so later appends/clears can't skew the snapshot
        times = list(_store.response_times)
        count = _store.total_requests
        errors = _store.total_errors

    avg_ms = round(sum(times) / len(times), 2) if times else 0.0
    min_ms = round(min(times), 2) if times else 0.0
    max_ms = round(max(times), 2) if times else 0.0

    return {
        "total_requests": count,
        "total_errors": errors,
        "error_rate_pct": round((errors / count) * 100, 2) if count else 0.0,
        "avg_response_time_ms": avg_ms,
        "min_response_time_ms": min_ms,
        "max_response_time_ms": max_ms,
    }


def reset() -> None:
    """Reset all counters (useful in tests)."""
    with _store._lock:
        _store.total_requests = 0
        _store.total_errors = 0
        _store.response_times.clear()
