"""Internal, unadvertised CLI commands that back the Bug Fix Kit skills.

These commands are intentionally hidden from ``bfk --help`` and the README.
Each skill calls its matching command so the deterministic create -> offset ->
execute -> read-log -> write pipeline is fixed in code rather than re-derived by
the model on every run:

- ``$bfk-capture`` -> ``bfk capture-run``
- ``$bfk-fix``     -> ``bfk fix-verify``
- ``$bfk-locate``  -> ``bfk locate-load``
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .mechanics import BfkError
from .mechanics.capture import run_capture_session
from .mechanics.fix import run_fix_verification
from .mechanics.http import DEFAULT_REQUEST_TIMEOUT_SECONDS
from .mechanics.locate import import_external_logs, load_capture_evidence


def _resolve_root(value: Path | None) -> Path:
    return (value or Path.cwd()).expanduser().resolve()


def _split_header(item: str) -> tuple[str, str]:
    if ":" not in item:
        raise argparse.ArgumentTypeError(f"header must be 'Key: Value': {item}")
    key, value = item.split(":", 1)
    return key.strip(), value.strip()


def _print_summary(summary: dict) -> int:
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


def _cmd_capture_run(args: argparse.Namespace) -> int:
    request_sample = args.request_sample or ""
    if args.request_sample_file:
        path = Path(args.request_sample_file).expanduser()
        try:
            request_sample = path.read_text()
        except OSError as exc:
            raise BfkError(f"cannot read --request-sample-file {path}: {exc.strerror or exc}") from exc
    headers = dict(args.header or [])
    result = run_capture_session(
        _resolve_root(args.root),
        list(args.params or []),
        base_url=args.base_url or "",
        log_files=list(args.log_file or []),
        default_headers=headers or None,
        request_sample=request_sample,
        endpoint=args.endpoint or "",
        after_request_wait_seconds=args.wait,
        timeout=args.timeout,
    )
    return _print_summary(result.to_summary())


def _cmd_fix_verify(args: argparse.Namespace) -> int:
    result = run_fix_verification(_resolve_root(args.root), timeout=args.timeout)
    summary = result.to_summary()
    summary["verification"] = True
    return _print_summary(summary)


def _cmd_locate_load(args: argparse.Namespace) -> int:
    return _print_summary(load_capture_evidence(_resolve_root(args.root)))


def _cmd_log_import(args: argparse.Namespace) -> int:
    return _print_summary(import_external_logs(_resolve_root(args.root), list(args.log_file or [])))


def register_internal_commands(subparsers: argparse._SubParsersAction) -> None:
    """Register the hidden skill-backing commands (no ``help=`` keeps them out of ``--help``)."""
    capture_run = subparsers.add_parser("capture-run")
    capture_run.add_argument("params", nargs="*")
    capture_run.add_argument("--root", type=Path, default=None)
    capture_run.add_argument("--base-url", dest="base_url", default="")
    capture_run.add_argument("--log-file", dest="log_file", action="append", default=[])
    capture_run.add_argument("--header", action="append", default=[], type=_split_header)
    capture_run.add_argument("--endpoint", default="")
    capture_run.add_argument("--request-sample", dest="request_sample", default="")
    capture_run.add_argument("--request-sample-file", dest="request_sample_file", type=Path, default=None)
    capture_run.add_argument("--wait", type=float, default=2.0)
    capture_run.add_argument("--timeout", type=float, default=DEFAULT_REQUEST_TIMEOUT_SECONDS)
    capture_run.set_defaults(func=_cmd_capture_run)

    fix_verify = subparsers.add_parser("fix-verify")
    fix_verify.add_argument("--root", type=Path, default=None)
    fix_verify.add_argument("--timeout", type=float, default=DEFAULT_REQUEST_TIMEOUT_SECONDS)
    fix_verify.set_defaults(func=_cmd_fix_verify)

    locate_load = subparsers.add_parser("locate-load")
    locate_load.add_argument("--root", type=Path, default=None)
    locate_load.set_defaults(func=_cmd_locate_load)

    log_import = subparsers.add_parser("log-import")
    log_import.add_argument("--root", type=Path, default=None)
    log_import.add_argument("--log-file", dest="log_file", action="append", required=True)
    log_import.set_defaults(func=_cmd_log_import)
