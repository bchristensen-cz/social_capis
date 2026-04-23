from __future__ import annotations

import responses

from src.hashing import event_id
from src.platforms.tiktok import ENDPOINT, TikTokClient


@responses.activate
def test_tiktok_success_payload_shape(sample_conversion):
    captured = {}

    def handler(request):
        import json

        captured["body"] = json.loads(request.body)
        captured["headers"] = dict(request.headers)
        return (200, {}, '{"code": 0, "message": "OK"}')

    responses.add_callback(responses.POST, ENDPOINT, callback=handler, content_type="application/json")

    client = TikTokClient(
        access_token="TOKEN", pixel_code="PIXEL", test_event_code="TEST123"
    )
    results = client.send([sample_conversion])

    assert len(results) == 1
    assert results[0].status == "ok"
    assert results[0].platform == "tiktok"
    assert results[0].event_id == event_id(sample_conversion.order_id, "tiktok")

    body = captured["body"]
    assert body["event_source"] == "offline"
    assert body["event_source_id"] == "PIXEL"
    assert body["test_event_code"] == "TEST123"
    event = body["data"][0]
    assert event["event"] == "Purchase"
    assert event["event_time"] == sample_conversion.epoch_seconds()
    assert event["user"]["email"] == sample_conversion.email_hash
    assert event["user"]["phone"] == sample_conversion.phone_hash
    assert event["properties"]["value"] == 42.50
    assert event["properties"]["order_id"] == "A00123456"
    assert captured["headers"].get("Access-Token") == "TOKEN"


@responses.activate
def test_tiktok_batches_across_1000_limit(sample_conversion):
    from dataclasses import replace

    rows = [replace(sample_conversion, order_id=f"O{i}") for i in range(1500)]

    responses.add(responses.POST, ENDPOINT, json={"code": 0}, status=200)

    client = TikTokClient("T", "P")
    results = client.send(rows)

    assert len(results) == 1500
    assert sum(1 for r in results if r.status == "ok") == 1500
    assert len(responses.calls) == 2


@responses.activate
def test_tiktok_4xx_is_not_retried(sample_conversion):
    responses.add(
        responses.POST,
        ENDPOINT,
        json={"code": 40001, "message": "bad request"},
        status=400,
    )

    client = TikTokClient("T", "P")
    results = client.send([sample_conversion])

    assert results[0].status == "error"
    assert len(responses.calls) == 1
