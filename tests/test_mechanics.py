from __future__ import annotations

import json
from pathlib import Path
from urllib.error import URLError

import pytest

from bug_fix_kit.mechanics import (
    BfkError,
    capture_offsets,
    create_issue,
    execute_request,
    latest_issue,
    load_runner_request,
    next_iteration_dir,
    read_since_offsets,
    write_project,
    write_run_artifacts,
)


def test_write_project_creates_project_knowledge(tmp_path: Path):
    project = write_project(
        tmp_path,
        base_url="http://localhost:8000",
        log_files=["logs/app.log"],
        default_headers={"Content-Type": "application/json"},
        auth_note="LOCAL_AUTH_TOKEN",
    )

    text = project.read_text()
    assert project == tmp_path / ".bfk" / "PROJECT.md"
    assert "http://localhost:8000" in text
    assert "logs/app.log" in text
    assert "LOCAL_AUTH_TOKEN" in text


def test_create_issue_scaffolds_runner_and_latest_issue(tmp_path: Path):
    write_project(tmp_path, base_url="http://localhost:8000", log_files=["logs/app.log"])

    issue = create_issue(tmp_path, "login failed", ["account=13900000000", "freeform"])

    assert issue.name.endswith("_login_failed")
    assert (issue / "issue.md").exists()
    runner = issue / "runner.py"
    assert runner.exists()
    assert (issue / "iterations").is_dir()
    assert latest_issue(tmp_path) == issue

    request = load_runner_request(runner)
    assert request["method"] == "POST"
    assert request["url"].startswith("http://localhost:8000")
    assert request["headers"]["Content-Type"] == "application/json"
    assert request["json"]["account"] == "13900000000"


def test_next_iteration_dir_never_overwrites(tmp_path: Path):
    issue = tmp_path / ".bfk" / "issues" / "20260625_120000_case"
    (issue / "iterations" / "001").mkdir(parents=True)

    next_dir = next_iteration_dir(issue)

    assert next_dir == issue / "iterations" / "002"
    assert next_dir.exists()
    assert (issue / "iterations" / "001").exists()


def test_log_offsets_read_only_appended_content_and_truncation(tmp_path: Path):
    log = tmp_path / "app.log"
    log.write_text("before\n")
    offsets = capture_offsets([log])
    log.write_text("before\nafter\n")
    assert read_since_offsets(offsets) == "after\n"

    offsets = capture_offsets([log])
    log.write_text("new\n")
    assert "new\n" in read_since_offsets(offsets)


def test_write_run_artifacts(tmp_path: Path):
    iteration = tmp_path / "001"
    response = {"status_code": 200, "headers": {}, "body": {"ok": True}, "body_text": None, "empty_body": False, "elapsed_ms": 1, "transport_error": None}

    write_run_artifacts(iteration, {"method": "GET", "url": "http://x"}, response, "log")

    assert json.loads((iteration / "request.json").read_text())["method"] == "GET"
    assert json.loads((iteration / "response.json").read_text())["body"] == {"ok": True}
    assert (iteration / "output.log").read_text() == "log"


def test_execute_request_normalizes_transport_errors(monkeypatch: pytest.MonkeyPatch):
    def fail(*_args, **_kwargs):
        raise URLError("connection refused")

    monkeypatch.setattr("bug_fix_kit.mechanics.urlopen", fail)

    response = execute_request({"method": "GET", "url": "http://127.0.0.1:1"}, timeout=1)

    assert response["status_code"] is None
    assert response["body"] is None
    assert response["body_text"] is None
    assert response["transport_error"]["type"] == "transport_error"
    assert "connection refused" in response["transport_error"]["message"]


def test_latest_issue_requires_existing_issue(tmp_path: Path):
    with pytest.raises(BfkError, match="No bfk issues"):
        latest_issue(tmp_path)


def test_generated_runner_runs_directly_and_prints_json(tmp_path: Path):
    import subprocess
    import sys

    write_project(tmp_path, base_url="http://localhost:8000", log_files=["logs/app.log"])
    issue = create_issue(tmp_path, "login_failed", ["account=13900000000"])

    result = subprocess.run(
        [sys.executable, str(issue / "runner.py")],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["json"]["account"] == "13900000000"


def test_latest_issue_uses_last_sorted_issue(tmp_path: Path):
    older = tmp_path / ".bfk" / "issues" / "20260625_120000_old"
    newer = tmp_path / ".bfk" / "issues" / "20260625_130000_new"
    older.mkdir(parents=True)
    newer.mkdir(parents=True)
    assert latest_issue(tmp_path) == newer


def test_next_iteration_dir_starts_at_001(tmp_path: Path):
    issue = tmp_path / ".bfk" / "issues" / "20260625_120000_case"
    issue.mkdir(parents=True)
    assert next_iteration_dir(issue).name == "001"


def test_load_runner_rejects_missing_or_malformed_build_request(tmp_path: Path):
    missing = tmp_path / "missing_build_request.py"
    missing.write_text("PARAMS = {}\n")
    with pytest.raises(BfkError, match="PARAMS and build_request"):
        load_runner_request(missing)

    malformed = tmp_path / "malformed_request.py"
    malformed.write_text("PARAMS = {}\ndef build_request(params):\n    return {'method': 'GET'}\n")
    with pytest.raises(BfkError, match="method and url"):
        load_runner_request(malformed)


def test_execute_request_normalizes_json_text_empty_and_http_error(monkeypatch: pytest.MonkeyPatch):
    class Headers(dict):
        def items(self):
            return super().items()

    class FakeResponse:
        def __init__(self, status: int, data: bytes, content_type: str):
            self.status = status
            self._data = data
            self.headers = Headers({"Content-Type": content_type, "X-Test": "yes"})

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self):
            return self._data

    responses = iter([
        FakeResponse(200, b'{"ok": true}', "application/json"),
        FakeResponse(200, b'plain text', "text/plain"),
        FakeResponse(204, b'', "text/plain"),
    ])
    monkeypatch.setattr("bug_fix_kit.mechanics.urlopen", lambda *_args, **_kwargs: next(responses))

    json_response = execute_request({"method": "GET", "url": "http://example.test"})
    assert json_response["body"] == {"ok": True}
    assert json_response["body_text"] is None
    assert json_response["headers"]["X-Test"] == "yes"

    text_response = execute_request({"method": "GET", "url": "http://example.test"})
    assert text_response["body"] is None
    assert text_response["body_text"] == "plain text"

    empty_response = execute_request({"method": "GET", "url": "http://example.test"})
    assert empty_response["empty_body"] is True
    assert empty_response["body"] is None
    assert empty_response["body_text"] is None


def test_log_truncation_is_explicit(tmp_path: Path):
    log = tmp_path / "app.log"
    log.write_text("before\nlonger\n")
    offsets = capture_offsets([log])
    log.write_text("new\n")

    output = read_since_offsets(offsets)

    assert "truncated" in output
    assert "new\n" in output


def test_project_headers_are_preserved_in_generated_runner(tmp_path: Path):
    write_project(
        tmp_path,
        base_url="http://localhost:8000",
        log_files=["logs/app.log"],
        default_headers={"Content-Type": "application/json", "Authorization": "Bearer devtoken"},
    )

    issue = create_issue(tmp_path, "auth_bug", ["account=1"])
    request = load_runner_request(issue / "runner.py")

    assert request["headers"]["Authorization"] == "Bearer devtoken"
    assert request["headers"]["Content-Type"] == "application/json"
    assert request["headers"]["X-BugFix-Issue"] == "auth_bug"
