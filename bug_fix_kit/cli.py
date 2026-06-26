from __future__ import annotations

import argparse
import importlib.util
import sys
import time
from pathlib import Path

from . import __version__
from .installer import InstallError, install_plugin
from .mechanics import (
    BfkError,
    RunnerExecutionError,
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


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _headers(items: list[str]) -> dict[str, str]:
    headers: dict[str, str] = {}
    for item in items:
        if "=" not in item:
            raise BfkError(f"header must be key=value: {item}")
        key, value = item.split("=", 1)
        headers[key] = value
    return headers


def _load_runner_config(runner_path: Path) -> tuple[list[Path], float]:
    spec = importlib.util.spec_from_file_location("bfk_issue_runner_config", runner_path)
    if spec is None or spec.loader is None:
        raise BfkError(f"Cannot load runner: {runner_path}")
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except Exception as exc:
        raise BfkError(f"failed to load runner.py: {exc}") from exc
    try:
        raw_log_files = getattr(module, "LOG_FILES", [])
        log_files = [Path(item) for item in raw_log_files]
        wait = float(getattr(module, "AFTER_REQUEST_WAIT_SECONDS", 0))
    except (TypeError, ValueError) as exc:
        raise BfkError(f"invalid runner config LOG_FILES or AFTER_REQUEST_WAIT_SECONDS: {exc}") from exc
    return log_files, wait


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="bfk",
        description="Bug Fix Kit local Codex plugin helper CLI.",
    )
    parser.add_argument("--version", action="version", version=f"bfk {__version__}")
    sub = parser.add_subparsers(dest="command")

    install = sub.add_parser("install", help="Install/register the local Codex plugin.")
    install.add_argument("--plugin-root", "--source-root", dest="source_root", type=Path, default=_repo_root())
    install.add_argument("--home", type=Path, default=None)
    install.add_argument("--marketplace", type=Path, default=None)
    install.add_argument("--yes", action="store_true", help="Replace existing installed plugin.")

    init = sub.add_parser("init-project", help="Create or update .bfk/PROJECT.md.")
    init.add_argument("--root", type=Path, default=Path("."))
    init.add_argument("--base-url", required=True)
    init.add_argument("--log-file", action="append", default=[])
    init.add_argument("--header", action="append", default=[])
    init.add_argument("--auth-note", default="")
    init.add_argument("--endpoint", default="", help="Request endpoint contract, for example 'POST /v1/responses'.")
    init.add_argument("--request-sample", default="", help="Raw curl request sample to preserve in .bfk/PROJECT.md.")
    init.add_argument(
        "--request-sample-file",
        "--sample-file",
        dest="request_sample_file",
        type=Path,
        default=None,
        help="File containing a raw curl request sample.",
    )
    init.add_argument("--request-name", default="default", help="Label for the preserved request sample.")
    init.add_argument("--timeout", type=float, default=120, help="Default request timeout documented for generated runners.")
    init.add_argument("--after-request-wait", type=float, default=2, help="Seconds to wait before reading logs.")
    init.add_argument("--evidence", action="append", default=[], help="Repository evidence line to preserve in PROJECT.md.")

    new = sub.add_parser("new", help="Create a bfk issue and runner.")
    new.add_argument("issue_name")
    new.add_argument("params", nargs="*")
    new.add_argument("--root", type=Path, default=Path("."))

    run = sub.add_parser("run", help="Run latest or specified issue runner and collect artifacts.")
    run.add_argument("issue_id", nargs="?")
    run.add_argument("--root", type=Path, default=Path("."))
    run.add_argument("--timeout", type=float, default=30)

    sub.add_parser("doctor", help="Check local package/plugin shell.")
    return parser


def _cmd_install(args: argparse.Namespace) -> int:
    result = install_plugin(
        source_root=args.source_root,
        home=args.home,
        marketplace_path=args.marketplace,
        yes=args.yes,
    )
    print(f"Installed plugin to {result.plugin_dir}")
    print(f"Marketplace: {result.marketplace_path}")
    print(result.next_steps)
    return 0


def _cmd_init_project(args: argparse.Namespace) -> int:
    request_sample = args.request_sample
    if args.request_sample_file:
        request_sample = args.request_sample_file.read_text()
    path = write_project(
        args.root,
        base_url=args.base_url,
        log_files=args.log_file or ["logs/app.log"],
        default_headers=_headers(args.header) if args.header else None,
        auth_note=args.auth_note,
        request_sample=request_sample,
        request_name=args.request_name,
        endpoint=args.endpoint,
        timeout_seconds=args.timeout,
        after_request_wait_seconds=args.after_request_wait,
        repository_evidence=args.evidence,
    )
    print(f"Wrote {path}")
    return 0


def _cmd_new(args: argparse.Namespace) -> int:
    issue = create_issue(args.root, args.issue_name, args.params)
    print(f"Created issue {issue}")
    return 0


def _write_runner_error_iteration(
    *,
    issue: Path,
    runner: Path,
    message: str,
    log_paths: list[Path] | None = None,
    wait: float = 0,
) -> Path:
    offsets = capture_offsets(log_paths or [])
    if wait:
        time.sleep(wait)
    logs = read_since_offsets(offsets)
    iteration = next_iteration_dir(issue)
    write_run_artifacts(
        iteration,
        {"runner": str(runner), "runner_error": message},
        {
            "status_code": None,
            "headers": {},
            "body": None,
            "body_text": None,
            "empty_body": False,
            "elapsed_ms": 0,
            "transport_error": {"type": "runner_error", "message": message},
        },
        logs,
    )
    return iteration


def _cmd_run(args: argparse.Namespace) -> int:
    root = args.root
    if args.issue_id:
        issue = root / ".bfk" / "issues" / args.issue_id
        if not issue.is_dir():
            raise BfkError(f"issue not found: {args.issue_id}")
    else:
        issue = latest_issue(root)
    runner = issue / "runner.py"
    if not runner.exists():
        raise BfkError(f"runner.py missing: {runner}")
    try:
        log_files, wait = _load_runner_config(runner)
        log_paths = [root / path for path in log_files]
    except BfkError as exc:
        iteration = _write_runner_error_iteration(issue=issue, runner=runner, message=str(exc))
        print(f"Wrote iteration {iteration}")
        return 0

    try:
        request = load_runner_request(runner)
    except (RunnerExecutionError, BfkError) as exc:
        iteration = _write_runner_error_iteration(
            issue=issue,
            runner=runner,
            message=str(exc),
            log_paths=log_paths,
            wait=wait,
        )
        print(f"Wrote iteration {iteration}")
        return 0

    offsets = capture_offsets(log_paths)
    response = execute_request(request, timeout=args.timeout)
    if wait:
        time.sleep(wait)
    logs = read_since_offsets(offsets)
    iteration = next_iteration_dir(issue)
    write_run_artifacts(iteration, request, response, logs)
    print(f"Wrote iteration {iteration}")
    return 0


def _cmd_doctor(_args: argparse.Namespace) -> int:
    root = _repo_root()
    manifest = root / ".codex-plugin" / "plugin.json"
    print(f"package root: {root}")
    print(f"plugin manifest: {'ok' if manifest.exists() else 'missing'} ({manifest})")
    print(f"skills dir: {'ok' if (root / 'skills').exists() else 'missing'}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "install":
            return _cmd_install(args)
        if args.command == "init-project":
            return _cmd_init_project(args)
        if args.command == "new":
            return _cmd_new(args)
        if args.command == "run":
            return _cmd_run(args)
        if args.command == "doctor":
            return _cmd_doctor(args)
        parser.print_help()
        return 0
    except (BfkError, InstallError) as exc:
        print(f"bfk: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
