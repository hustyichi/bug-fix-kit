from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

INTERNAL_COMMANDS = ["capture-run", "fix-verify", "locate-load"]


def run_bfk(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src") + os.pathsep + env.get("PYTHONPATH", "")
    return subprocess.run(
        [sys.executable, "-m", "bug_fix_kit", *args],
        cwd=cwd,
        env=env,
        text=True,
        capture_output=True,
    )


def _make_server(log_path: Path) -> ThreadingHTTPServer:
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:  # noqa: N802 - http.server API
            length = int(self.headers.get("Content-Length", 0))
            self.rfile.read(length)
            with log_path.open("a", encoding="utf-8") as handle:
                handle.write(f"POST {self.path} 401\n")
            body = json.dumps({"ok": False, "error": "login failed"}).encode()
            self.send_response(401)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *_args) -> None:  # silence stderr noise
            return

    return ThreadingHTTPServer(("127.0.0.1", 0), Handler)


@pytest.fixture()
def local_service(tmp_path: Path):
    log_path = tmp_path / "app.log"
    server = _make_server(log_path)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server.server_address[1]
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_internal_commands_are_hidden_from_help(tmp_path: Path):
    result = run_bfk(tmp_path, "--help")

    assert result.returncode == 0
    for command in INTERNAL_COMMANDS:
        assert command not in result.stdout


def test_capture_run_command_name_and_summary_shape(tmp_path: Path, local_service):
    port = local_service

    result = run_bfk(
        tmp_path,
        "capture-run",
        "account=13900000000",
        "--base-url",
        f"http://127.0.0.1:{port}",
        "--endpoint",
        "POST /login",
        "--log-file",
        "app.log",
        "--wait",
        "0",
    )

    assert result.returncode == 0, result.stderr
    summary = json.loads(result.stdout)
    assert set(summary) == {
        "capture_dir",
        "replayed",
        "request",
        "response_status",
        "transport_error",
        "log_files",
        "missing_log_files",
        "output_log_name",
        "output_log_bytes",
        "artifacts",
    }
    assert summary["replayed"] is False
    assert summary["request"] == {
        "method": "POST",
        "url": f"http://127.0.0.1:{port}/login",
    }
    assert summary["response_status"] == 401
    assert summary["output_log_name"] == "output.log"
    assert set(summary["artifacts"]) == {"runner", "request", "response", "output_log"}

    capture_dir = tmp_path / ".bfk"
    for name in ("runner.py", "request.json", "response.json", "output.log"):
        assert (capture_dir / name).exists()


def test_fix_verify_command_name_and_summary_shape(tmp_path: Path, local_service):
    port = local_service
    capture = run_bfk(
        tmp_path,
        "capture-run",
        "account=13900000000",
        "--base-url",
        f"http://127.0.0.1:{port}",
        "--endpoint",
        "POST /login",
        "--log-file",
        "app.log",
        "--wait",
        "0",
    )
    assert capture.returncode == 0, capture.stderr

    result = run_bfk(tmp_path, "fix-verify", "--timeout", "5")

    assert result.returncode == 0, result.stderr
    summary = json.loads(result.stdout)
    assert summary["verification"] is True
    assert summary["output_log_name"] == "fix_output.log"
    assert summary["response_status"] == 401
    assert set(summary["artifacts"]) == {"runner", "request", "response", "output_log"}

    capture_dir = tmp_path / ".bfk"
    assert (capture_dir / "fix_output.log").exists()
    # The original capture log must not be overwritten by verification.
    assert (capture_dir / "output.log").exists()


def test_locate_load_command_name_and_summary_shape(tmp_path: Path):
    result = run_bfk(tmp_path, "locate-load")

    assert result.returncode == 0, result.stderr
    summary = json.loads(result.stdout)
    assert set(summary) == {
        "capture_dir",
        "has_request",
        "has_response",
        "has_output_log",
        "request",
        "response",
        "output_log",
        "output_log_bytes",
        "root_cause_exists",
        "missing_evidence",
    }
    assert summary["has_request"] is False
    assert summary["missing_evidence"] == [
        "request.json",
        "response.json",
        "output.log",
    ]


def test_capture_run_missing_sample_file_is_normalized(tmp_path: Path):
    result = run_bfk(
        tmp_path,
        "capture-run",
        "--request-sample-file",
        str(tmp_path / "missing.txt"),
    )

    assert result.returncode == 1
    assert "Traceback" not in result.stderr
    assert result.stderr.startswith("bfk: ")
    assert "cannot read --request-sample-file" in result.stderr


def test_capture_run_malformed_header_is_normalized(tmp_path: Path):
    result = run_bfk(
        tmp_path,
        "capture-run",
        "account=1",
        "--header",
        "BadHeader",
    )

    assert result.returncode == 2
    assert "Traceback" not in result.stderr
    assert "--header" in result.stderr
