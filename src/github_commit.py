from __future__ import annotations

import base64

import requests

from .observability import get_logger
from .retry import NonRetryableError, retryable_request

log = get_logger(__name__)

API = "https://api.github.com"
_HEADERS_ACCEPT = "application/vnd.github+json"
_HEADERS_VERSION = "2022-11-28"


def _headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Accept": _HEADERS_ACCEPT,
        "X-GitHub-Api-Version": _HEADERS_VERSION,
    }


@retryable_request
def _get_existing_sha(
    session: requests.Session, repo: str, path: str, branch: str, token: str
) -> str | None:
    url = f"{API}/repos/{repo}/contents/{path}"
    r = session.get(url, headers=_headers(token), params={"ref": branch}, timeout=30)
    if r.status_code == 404:
        return None
    if r.status_code == 401 or r.status_code == 403:
        raise NonRetryableError(f"github auth error: {r.status_code} {r.text[:200]}")
    r.raise_for_status()
    payload = r.json()
    if isinstance(payload, dict):
        return payload.get("sha")
    return None


@retryable_request
def _put_contents(
    session: requests.Session,
    repo: str,
    path: str,
    body: dict,
    token: str,
) -> dict:
    url = f"{API}/repos/{repo}/contents/{path}"
    r = session.put(url, headers=_headers(token), json=body, timeout=30)
    if r.status_code in (401, 403):
        raise NonRetryableError(f"github auth error: {r.status_code} {r.text[:200]}")
    if r.status_code == 422:
        raise NonRetryableError(f"github 422 validation: {r.text[:200]}")
    r.raise_for_status()
    return r.json()


def commit_file(
    repo: str,
    path: str,
    content: bytes,
    message: str,
    token: str,
    branch: str = "main",
    session: requests.Session | None = None,
) -> dict:
    s = session or requests.Session()
    existing_sha = _get_existing_sha(s, repo, path, branch, token)
    body: dict = {
        "message": message,
        "content": base64.b64encode(content).decode("ascii"),
        "branch": branch,
    }
    if existing_sha:
        body["sha"] = existing_sha
    log.info(
        "github_commit",
        extra={"repo": repo, "path": path, "bytes": len(content), "overwrite": bool(existing_sha)},
    )
    return _put_contents(s, repo, path, body, token)
