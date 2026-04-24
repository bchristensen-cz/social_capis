from __future__ import annotations

from collections.abc import Sequence

import requests

from ..hashing import event_id
from ..models import Conversion, SendResult
from ..observability import get_logger, log_send
from ..retry import NonRetryableError, retryable_request
from .base import chunk

NAME = "tiktok"
ENDPOINT = "https://business-api.tiktok.com/open_api/v1.3/event/track/"
BATCH = 1000

log = get_logger(__name__)


class TikTokClient:
    name = NAME

    def __init__(
        self,
        access_token: str,
        pixel_code: str,
        test_event_code: str = "",
        timeout: int = 30,
        session: requests.Session | None = None,
    ):
        self._token = access_token
        self._pixel = pixel_code
        self._test = test_event_code
        self._timeout = timeout
        self._session = session or requests.Session()

    def _build_event(self, c: Conversion) -> dict:
        user: dict[str, str] = {}
        if c.email_hash:
            user["email"] = c.email_hash
        if c.phone_hash:
            user["phone"] = c.phone_hash
        return {
            "event": c.event_name,
            "event_time": c.epoch_seconds(),
            "event_id": event_id(c.order_id, NAME),
            "user": user,
            "properties": {
                "value": c.value,
                "currency": c.currency,
                "order_id": c.order_id,
            },
        }

    def _build_body(self, batch: Sequence[Conversion]) -> dict:
        body: dict = {
            "event_source": "offline",
            "event_source_id": self._pixel,
            "data": [self._build_event(c) for c in batch],
        }
        if self._test:
            body["test_event_code"] = self._test
        return body

    @retryable_request
    def _post(self, body: dict) -> requests.Response:
        r = self._session.post(
            ENDPOINT,
            headers={"Access-Token": self._token, "Content-Type": "application/json"},
            json=body,
            timeout=self._timeout,
        )
        if 400 <= r.status_code < 500 and r.status_code != 429:
            raise NonRetryableError(f"tiktok 4xx: {r.status_code} {r.text[:200]}")
        r.raise_for_status()
        payload = r.json()
        if payload.get("code") not in (0, None):
            raise NonRetryableError(f"tiktok api error: {payload}")
        return r

    def send(self, conversions: Sequence[Conversion]) -> list[SendResult]:
        results: list[SendResult] = []
        for batch in chunk(conversions, BATCH):
            body = self._build_body(batch)
            try:
                r = self._post(body)
                http_code = r.status_code
                for c in batch:
                    eid = event_id(c.order_id, NAME)
                    results.append(
                        SendResult(NAME, c.order_id, eid, "ok", http_code=http_code)
                    )
                    log_send(log, NAME, c.order_id, eid, "ok", http_code=http_code)
            except Exception as e:
                err = str(e)[:500]
                for c in batch:
                    eid = event_id(c.order_id, NAME)
                    results.append(
                        SendResult(NAME, c.order_id, eid, "error", error=err)
                    )
                    log_send(log, NAME, c.order_id, eid, "error", error=err)
        return results
