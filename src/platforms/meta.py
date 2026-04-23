from __future__ import annotations

from collections.abc import Sequence

import requests

from ..hashing import event_id
from ..models import Conversion, SendResult
from ..observability import get_logger, log_send
from ..retry import NonRetryableError, retryable_request
from .base import chunk

NAME = "meta"
API_VERSION = "v19.0"
BATCH = 1000

log = get_logger(__name__)


class MetaClient:
    name = NAME

    def __init__(
        self,
        access_token: str,
        dataset_id: str,
        test_event_code: str = "",
        api_version: str = API_VERSION,
        timeout: int = 30,
        session: requests.Session | None = None,
    ):
        self._token = access_token
        self._dataset = dataset_id
        self._test = test_event_code
        self._endpoint = f"https://graph.facebook.com/{api_version}/{dataset_id}/events"
        self._timeout = timeout
        self._session = session or requests.Session()

    def _build_event(self, c: Conversion) -> dict:
        return {
            "event_name": c.event_name,
            "event_time": c.epoch_seconds(),
            "action_source": "physical_store",
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
        body: dict = {
            "data": [self._build_event(c) for c in batch],
            "access_token": self._token,
        }
        if self._test:
            body["test_event_code"] = self._test
        return body

    @retryable_request
    def _post(self, body: dict) -> requests.Response:
        r = self._session.post(
            self._endpoint,
            json=body,
            timeout=self._timeout,
        )
        if r.status_code == 400:
            try:
                err = r.json().get("error", {})
                if err.get("code") == 190:
                    raise NonRetryableError(f"meta auth error (190): {err}")
            except ValueError:
                pass
            raise NonRetryableError(f"meta 400: {r.text[:200]}")
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
