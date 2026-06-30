from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from .installer import InstallError, install_plugin, resolve_payload_source
from .internal_commands import register_internal_commands
from .mechanics import BfkError


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="bfk",
        description="Bug Fix Kit local Codex plugin management CLI.",
    )
    parser.add_argument("--version", action="version", version=f"bfk {__version__}")
    # metavar hides the choice list so internal commands stay out of --help.
    sub = parser.add_subparsers(dest="command", metavar="<command>")

    install = sub.add_parser("install", help="Install/register the local Codex plugin.")
    install.add_argument("--plugin-root", "--source-root", dest="source_root", type=Path, default=None)
    install.add_argument("--home", type=Path, default=None)
    install.add_argument("--marketplace", type=Path, default=None)
    install.add_argument("--yes", action="store_true", help="Replace existing installed plugin.")

    doctor = sub.add_parser("doctor", help="Check local package/plugin shell.")
    doctor.add_argument("--plugin-root", "--source-root", dest="source_root", type=Path, default=None)

    register_internal_commands(sub)
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


def _cmd_doctor(args: argparse.Namespace) -> int:
    payload = resolve_payload_source(args.source_root)
    print(f"payload source: {payload.kind}")
    print(f"payload root: {payload.display_root}")
    print(f"plugin manifest: ok ({payload.display_root}/.codex-plugin/plugin.json)")
    print(f"skills dir: ok ({payload.display_root}/skills)")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        handler = getattr(args, "func", None)
        if handler is not None:
            return handler(args)
        if args.command == "install":
            return _cmd_install(args)
        if args.command == "doctor":
            return _cmd_doctor(args)
        parser.print_help()
        return 0
    except (InstallError, BfkError) as exc:
        print(f"bfk: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
