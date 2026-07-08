from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from bug_fix_kit.cli import build_parser
from bug_fix_kit.mechanics.http import DEFAULT_REQUEST_TIMEOUT_SECONDS

ROOT = Path(__file__).resolve().parents[1]

INTERNAL_COMMANDS = ["capture-run", "fix-verify", "locate-load", "log-import", "probe-run", "probe-revert"]


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


def test_internal_execution_defaults_allow_long_running_tasks():
    parser = build_parser()

    capture_args = parser.parse_args([
        "capture-run",
        "--base-url",
        "http://127.0.0.1:8000",
        "--log-file",
        "app.log",
    ])
    verify_args = parser.parse_args(["fix-verify"])

    assert DEFAULT_REQUEST_TIMEOUT_SECONDS >= 300
    assert capture_args.timeout == DEFAULT_REQUEST_TIMEOUT_SECONDS
    assert verify_args.timeout == DEFAULT_REQUEST_TIMEOUT_SECONDS


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
    assert not (capture_dir / "archive").exists()


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
        "probe_session",
        "root_cause_exists",
        "missing_evidence",
    }
    assert summary["has_request"] is False
    assert summary["probe_session"] is None
    assert summary["missing_evidence"] == [
        "request.json",
        "response.json",
        "output.log",
    ]


def test_log_import_writes_external_logs_to_default_output_log(tmp_path: Path):
    external = tmp_path / "external.log"
    external.write_text("external failure\nstack trace\n")
    bfk = tmp_path / ".bfk"
    bfk.mkdir()
    for name in ("runner.py", "request.json", "response.json", "output.log", "root-cause.md", "fix-plan.md"):
        (bfk / name).write_text("stale")

    result = run_bfk(tmp_path, "log-import", "--log-file", str(external))

    assert result.returncode == 0, result.stderr
    summary = json.loads(result.stdout)
    assert summary["log_files"] == [str(external)]
    assert summary["missing_log_files"] == []
    assert summary["output_log_bytes"] == len("external failure\nstack trace\n".encode())
    assert (bfk / "output.log").read_text() == "external failure\nstack trace\n"
    assert not (bfk / "runner.py").exists()
    assert not (bfk / "request.json").exists()
    assert not (bfk / "response.json").exists()
    assert not (bfk / "root-cause.md").exists()
    assert not (bfk / "fix-plan.md").exists()

    loaded = run_bfk(tmp_path, "locate-load")
    assert loaded.returncode == 0, loaded.stderr
    evidence = json.loads(loaded.stdout)
    assert evidence["has_output_log"] is True
    assert evidence["output_log"] == "external failure\nstack trace\n"
    assert evidence["missing_evidence"] == ["request.json", "response.json"]


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


def _make_probed_server(log_path: Path) -> ThreadingHTTPServer:
    """Service variant that also writes probe marker lines, as if instrumented."""

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:  # noqa: N802 - http.server API
            length = int(self.headers.get("Content-Length", 0))
            self.rfile.read(length)
            with log_path.open("a", encoding="utf-8") as handle:
                handle.write(f"POST {self.path} 401\n")
                handle.write("[BFK-PROBE] enter login handler\n")
            body = json.dumps({"ok": False, "error": "login failed"}).encode()
            self.send_response(401)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *_args) -> None:
            return

    return ThreadingHTTPServer(("127.0.0.1", 0), Handler)


@pytest.fixture()
def probed_service(tmp_path: Path):
    log_path = tmp_path / "app.log"
    server = _make_probed_server(log_path)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server.server_address[1]
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def _capture(tmp_path: Path, port: int) -> None:
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


def test_probe_run_revert_roundtrip(tmp_path: Path, probed_service):
    port = probed_service
    _capture(tmp_path, port)

    app = tmp_path / "app.py"
    app.write_text('def login():\n    print("[BFK-PROBE] enter login handler")  # BFK-PROBE\n    return 401\n')

    result = run_bfk(tmp_path, "probe-run", "--file", "app.py")

    assert result.returncode == 0, result.stderr
    summary = json.loads(result.stdout)
    assert summary["output_log_name"] == "output.log"
    assert summary["probe"] == {
        "marker": "BFK-PROBE",
        "round": 1,
        "max_rounds": 2,
        "files": ["app.py"],
        "sentinel_seen": True,
    }
    # The probe replay refreshes the unified evidence log in place.
    assert "[BFK-PROBE] enter login handler" in (tmp_path / ".bfk" / "output.log").read_text()
    assert not (tmp_path / ".bfk" / "probe_output.log").exists()

    status = json.loads(run_bfk(tmp_path, "locate-load").stdout)["probe_session"]
    assert status["reverted"] is False
    assert status["residue_files"] == ["app.py"]

    # A new capture must refuse to start while probe residue remains.
    blocked = run_bfk(
        tmp_path,
        "capture-run",
        "account=1",
        "--base-url",
        f"http://127.0.0.1:{port}",
        "--log-file",
        "app.log",
    )
    assert blocked.returncode == 1
    assert "Probe residue detected" in blocked.stderr
    assert "$bfk-probe --revert" in blocked.stderr

    revert = run_bfk(tmp_path, "probe-revert")
    assert revert.returncode == 0, revert.stderr
    revert_summary = json.loads(revert.stdout)
    assert revert_summary["clean"] is True
    assert revert_summary["residue_files"] == []
    assert revert_summary["reverted_files"] == [{"file": "app.py", "method": "strip"}]
    assert "BFK-PROBE" not in app.read_text()
    assert 'def login():' in app.read_text()

    status = json.loads(run_bfk(tmp_path, "locate-load").stdout)["probe_session"]
    assert status["reverted"] is True
    assert status["residue_files"] == []

    evidence = json.loads(run_bfk(tmp_path, "locate-load").stdout)
    assert "[BFK-PROBE] enter login handler" in evidence["output_log"]
    assert evidence["probe_session"]["reverted"] is True


def test_probe_run_requires_existing_capture(tmp_path: Path):
    (tmp_path / "app.py").write_text("x = 1  # BFK-PROBE\n")

    result = run_bfk(tmp_path, "probe-run", "--file", "app.py")

    assert result.returncode == 1
    assert "No bfk capture found" in result.stderr


def test_probe_run_enforces_round_limit(tmp_path: Path, probed_service):
    port = probed_service
    _capture(tmp_path, port)
    app = tmp_path / "app.py"
    app.write_text("x = 1  # BFK-PROBE\n")

    assert run_bfk(tmp_path, "probe-run", "--file", "app.py").returncode == 0
    assert run_bfk(tmp_path, "probe-run", "--file", "app.py").returncode == 0
    third = run_bfk(tmp_path, "probe-run", "--file", "app.py")

    assert third.returncode == 1
    assert "Probe round limit reached" in third.stderr

    # Reverting resets the session so probing can start again.
    assert run_bfk(tmp_path, "probe-revert").returncode == 0
    app.write_text("x = 1  # BFK-PROBE\n")
    again = run_bfk(tmp_path, "probe-run", "--file", "app.py")
    assert again.returncode == 0
    assert json.loads(again.stdout)["probe"]["round"] == 1


def test_probe_run_requires_marker_in_files(tmp_path: Path, probed_service):
    port = probed_service
    _capture(tmp_path, port)
    (tmp_path / "app.py").write_text("x = 1\n")

    result = run_bfk(tmp_path, "probe-run", "--file", "app.py")

    assert result.returncode == 1
    assert "No BFK-PROBE line found" in result.stderr
