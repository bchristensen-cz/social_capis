from __future__ import annotations

import requests
from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)


class NonRetryableError(RuntimeError):
    """Raised for 4xx responses that should not be retried (e.g. bad token, bad request)."""


def _should_retry(exc: BaseException) -> bool:
    if isinstance(exc, NonRetryableError):
        return False
    if isinstance(exc, requests.Timeout):
        return True
    if isinstance(exc, requests.ConnectionError):
        return True
    if isinstance(exc, requests.HTTPError):
        resp = exc.response
        if resp is None:
            return True
        code = resp.status_code
        return code == 429 or 500 <= code < 600
    return False


retryable_request = retry(
    reraise=True,
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=1, max=30),
    retry=retry_if_exception(_should_retry),
)
