from __future__ import annotations

import os
import resource
from typing import Any

from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest


CONCURRENT_CALLS = Gauge("voice_concurrent_calls", "Active concurrent phone calls")
ACTIVE_SESSIONS = Gauge("voice_active_sessions", "Active call sessions")
CALLS_STARTED = Counter("voice_calls_started_total", "Total calls started", ["tenant_id"])
CALLS_ENDED = Counter(
    "voice_calls_ended_total", "Total calls ended", ["tenant_id", "reason"]
)
INTERRUPTIONS = Counter(
    "voice_interruptions_total", "Caller barge-in interruptions", ["tenant_id"]
)
TOOL_CALLS = Counter(
    "voice_tool_calls_total", "Tool invocations", ["tenant_id", "tool", "status"]
)
ERRORS = Counter("voice_errors_total", "Application errors", ["component"])
RESPONSE_LATENCY = Histogram(
    "voice_response_latency_seconds",
    "Time from caller audio end to first AI audio out",
    buckets=(0.1, 0.25, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0, 5.0),
)
RECONNECTS = Counter("voice_reconnects_total", "Provider reconnects", ["tenant_id"])


def metrics_payload() -> tuple[bytes, str]:
    return generate_latest(), CONTENT_TYPE_LATEST


def memory_usage_mb() -> float:
    usage = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    # macOS reports bytes; Linux reports kilobytes
    if os.uname().sysname == "Darwin":
        return usage / (1024 * 1024)
    return usage / 1024


def snapshot() -> dict[str, Any]:
    return {
        "concurrent_calls": CONCURRENT_CALLS._value.get(),
        "active_sessions": ACTIVE_SESSIONS._value.get(),
        "memory_usage_mb": round(memory_usage_mb(), 2),
    }
