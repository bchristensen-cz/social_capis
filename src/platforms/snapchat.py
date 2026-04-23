from __future__ import annotations

from collections.abc import Sequence

import requests

from ..hashing import event_id
from ..models import Conversion, SendResult
from ..observability import get_logger, log_send
from ..retry import NonRetryableError, retryable_request
from .base import chunk

NAME = "snapchat"
BATCH = 2000

log = get_logger(__name__)


class SnapchatClient:
    name = NAME

    def __init__(
        self,
        access_token: str,
        pixel_id: str,
        test_event_code: str = "",
        timeout: int = 30,
        session: requests.Session | None = None,
    ):
        self._token = access_token
        self._pixel = pixel_id
        self._test = test_event_code
        self._endpoint = f"https://tr.snapchat.com/v3/{pixel_id}/events"
        self._timeout = timeout
        self._session = session or requests.Session()

    def _build_event(self, c: Conversion) -> dict:
        return {
            "event_name": c.event_name.upper(),
            "event_time": c.epoch_seconds(),
            "action_source": "OFFLINE",
            "event_id": event_id(c.order_id, NAME),
            "user_data": {
                "em": [c.email_hash] if c.email_hash else [],
                "ph": [c.phone_hash] if c.phone_hash else [],
            },
            "custom_data": {
                "value": c.value,
                "currency": c.currency,
                "order_id": c.order_id,
            },
        }

    def _build_body(self, batch: Sequence[Conversion]) -> dict:
        body: dict = {"data": [self._build_event(c) for c in batch]}
        if self._test:
            body["test_event_code"] = self._test
        return body

    @retryable_request
    def _post(self, body: dict) -> requests.Response:
        r = self._session.post(
            self._endpoint,
            headers={
                "Authorization": f"Bearer {self._token}",
                "Content-Type": "application/json",
            },
            json=body,
            timeout=self._timeout,
        )
        if r.status_code == 401 or r.status_code == 403:
            raise NonRetryableError(f"snap auth error: {r.status_code} {r.text[:200]}")
        if r.status_code == 400:
            raise NonRetryableError(f"snap 400: {r.text[:200]}")
        r.raise_for_status()
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
