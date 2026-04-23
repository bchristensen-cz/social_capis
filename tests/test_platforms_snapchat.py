from __future__ import annotations

import json

import responses

from src.platforms.snapchat import SnapchatClient


def _endpoint(pixel_id: str) -> str:
    return f"https://tr.snapchat.com/v3/{pixel_id}/events"


@responses.activate
def test_snap_success_payload_shape(sample_conversion):
    captured = {}

    def handler(request):
        captured["body"] = json.loads(request.body)
        captured["headers"] = dict(request.headers)
        return (200, {}, '{"status": "ok"}')

    responses.add_callback(
        responses.POST, _endpoint("PIX"), callback=handler, content_type="application/json"
    )

    client = SnapchatClient(access_token="TK", pixel_id="PIX")
    results = client.send([sample_conversion])

    assert results[0].status == "ok"

    body = captured["body"]
    event = body["data"][0]
    assert event["event_name"] == "PURCHASE"
    assert event["action_source"] == "OFFLINE"
    assert event["user_data"]["em"] == [sample_conversion.email_hash]
    assert captured["headers"].get("Authorization") == "Bearer TK"


@responses.activate
def test_snap_401_is_not_retried(sample_conversion):
    responses.add(responses.POST, _endpoint("PIX"), status=401)

    client = SnapchatClient("TK", "PIX")
    results = client.send([sample_conversion])

    assert results[0].status == "error"
    assert len(responses.calls) == 1
