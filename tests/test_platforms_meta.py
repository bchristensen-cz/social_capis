from __future__ import annotations

import json

import responses

from src.platforms.meta import API_VERSION, MetaClient


def _endpoint(dataset_id: str) -> str:
    return f"https://graph.facebook.com/{API_VERSION}/{dataset_id}/events"


@responses.activate
def test_meta_success_payload_shape(sample_conversion):
    captured = {}

    def handler(request):
        captured["body"] = json.loads(request.body)
        return (200, {}, '{"events_received": 1}')

    responses.add_callback(
        responses.POST, _endpoint("DATASET"), callback=handler, content_type="application/json"
    )

    client = MetaClient(access_token="T", dataset_id="DATASET", test_event_code="TEST")
    results = client.send([sample_conversion])

    assert results[0].status == "ok"

    body = captured["body"]
    event = body["data"][0]
    assert event["event_name"] == "Purchase"
    assert event["action_source"] == "physical_store"
    assert event["user_data"]["em"] == [sample_conversion.email_hash]
    assert event["user_data"]["ph"] == [sample_conversion.phone_hash]
    assert event["custom_data"]["order_id"] == "A00123456"
    assert body["access_token"] == "T"
    assert body["test_event_code"] == "TEST"


@responses.activate
def test_meta_token_error_is_not_retried(sample_conversion):
    responses.add(
        responses.POST,
        _endpoint("DATASET"),
        json={"error": {"code": 190, "message": "invalid token"}},
        status=400,
    )

    client = MetaClient("T", "DATASET")
    results = client.send([sample_conversion])

    assert results[0].status == "error"
    assert "190" in (results[0].error or "")
    assert len(responses.calls) == 1


@responses.activate
def test_meta_5xx_retries_then_succeeds(sample_conversion):
    responses.add(responses.POST, _endpoint("DATASET"), status=503)
    responses.add(responses.POST, _endpoint("DATASET"), json={"events_received": 1}, status=200)

    client = MetaClient("T", "DATASET")
    results = client.send([sample_conversion])

    assert results[0].status == "ok"
    assert len(responses.calls) == 2
