from __future__ import annotations

from dataclasses import replace

from src.main import (
    any_platform_fully_down,
    compute_error_rate,
    failures_to_jsonl,
    group_failures,
)
from src.models import SendResult


def _ok(platform: str, order_id: str) -> SendResult:
    return SendResult(platform, order_id, "eid-" + order_id, "ok", http_code=200)


def _err(platform: str, order_id: str, error: str = "boom") -> SendResult:
    return SendResult(platform, order_id, "eid-" + order_id, "error", error=error)


def test_compute_error_rate_empty_is_zero():
    assert compute_error_rate([]) == 0.0


def test_compute_error_rate_mixed():
    results = [_ok("tiktok", "A"), _err("meta", "A"), _ok("snap", "A"), _err("tiktok", "B")]
    assert compute_error_rate(results) == 0.5


def test_any_platform_fully_down_detects():
    results = [_ok("tiktok", "A"), _err("meta", "A"), _err("meta", "B")]
    assert any_platform_fully_down(results) == "meta"


def test_any_platform_fully_down_none():
    results = [_ok("tiktok", "A"), _ok("meta", "A")]
    assert any_platform_fully_down(results) is None


def test_group_failures_and_jsonl(sample_conversion):
    c2 = replace(sample_conversion, order_id="A00123457")
    conversions = [sample_conversion, c2]
    results = [
        _ok("tiktok", sample_conversion.order_id),
        _err("meta", sample_conversion.order_id, error="meta boom"),
        _ok("snap", sample_conversion.order_id),
        _err("meta", c2.order_id, error="meta boom2"),
        _ok("tiktok", c2.order_id),
        _ok("snap", c2.order_id),
    ]

    grouped = group_failures(conversions, results)
    assert set(grouped.keys()) == {"meta"}
    assert len(grouped["meta"]) == 2

    jsonl = failures_to_jsonl(grouped).decode()
    lines = [line for line in jsonl.splitlines() if line]
    assert len(lines) == 2
    assert "meta boom" in lines[0] or "meta boom" in lines[1]
