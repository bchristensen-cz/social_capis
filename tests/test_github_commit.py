from __future__ import annotations

import base64
import json

import responses

from src.github_commit import API, commit_file, file_exists


def _url(repo: str, path: str) -> str:
    return f"{API}/repos/{repo}/contents/{path}"


@responses.activate
def test_commit_new_file_no_sha():
    repo, path = "owner/repo", "data/2026-04-22.jsonl"
    content = b'{"order_id":"A1"}\n'

    responses.add(responses.GET, _url(repo, path), status=404)
    put_captured = {}

    def put_handler(request):
        put_captured["body"] = json.loads(request.body)
        return (201, {}, '{"content": {"sha": "abc"}}')

    responses.add_callback(
        responses.PUT, _url(repo, path), callback=put_handler, content_type="application/json"
    )

    commit_file(repo, path, content, "data: foo", token="T")

    body = put_captured["body"]
    assert "sha" not in body
    assert body["message"] == "data: foo"
    assert base64.b64decode(body["content"]) == content
    assert body["branch"] == "main"


@responses.activate
def test_commit_overwrite_includes_existing_sha():
    repo, path = "owner/repo", "data/2026-04-22.jsonl"

    responses.add(responses.GET, _url(repo, path), json={"sha": "deadbeef"}, status=200)
    put_captured = {}

    def put_handler(request):
        put_captured["body"] = json.loads(request.body)
        return (200, {}, '{"content": {"sha": "new"}}')

    responses.add_callback(
        responses.PUT, _url(repo, path), callback=put_handler, content_type="application/json"
    )

    commit_file(repo, path, b"x", "msg", token="T")
    assert put_captured["body"]["sha"] == "deadbeef"


@responses.activate
def test_commit_auth_error_does_not_retry():
    import pytest

    from src.retry import NonRetryableError

    repo, path = "owner/repo", "data/2026-04-22.jsonl"
    responses.add(responses.GET, _url(repo, path), status=401)

    with pytest.raises(NonRetryableError):
        commit_file(repo, path, b"x", "msg", token="BAD")

    assert len(responses.calls) == 1


@responses.activate
def test_file_exists_true_when_present():
    repo, path = "owner/repo", "data/2026-08-21.jsonl"
    responses.add(responses.GET, _url(repo, path), json={"sha": "deadbeef"}, status=200)
    assert file_exists(repo, path, token="T") is True


@responses.activate
def test_file_exists_false_on_404():
    repo, path = "owner/repo", "data/2026-08-21.jsonl"
    responses.add(responses.GET, _url(repo, path), status=404)
    assert file_exists(repo, path, token="T") is False
