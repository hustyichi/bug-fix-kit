from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from pathlib import Path

PLUGIN_NAME = "bug-fix-kit"
REQUIRED_SKILLS = ("bfk-init", "bfk-new", "bfk-run", "bfk-diagnose", "bfk-fix")
EXCLUDED_NAMES = {".git", ".omx", ".bfk", ".venv", "__pycache__", ".pytest_cache", "build", "dist"}


class InstallError(RuntimeError):
    pass


@dataclass(frozen=True)
class InstallResult:
    plugin_dir: Path
    marketplace_path: Path
    next_steps: str


def _canonical_source_root(source_root: Path) -> Path:
    packaged = source_root / "bug_fix_kit" / "plugin"
    if (packaged / ".codex-plugin" / "plugin.json").exists():
        return packaged
    return source_root


def _validate_source(source_root: Path) -> None:
    manifest_path = source_root / ".codex-plugin" / "plugin.json"
    if not manifest_path.exists():
        raise InstallError(f"missing plugin.json at {manifest_path}")
    try:
        manifest = json.loads(manifest_path.read_text())
    except json.JSONDecodeError as exc:
        raise InstallError(f"invalid plugin.json: {exc}") from exc
    if manifest.get("name") != PLUGIN_NAME:
        raise InstallError(f"plugin.json name must be {PLUGIN_NAME!r}")
    for skill in REQUIRED_SKILLS:
        if not (source_root / "skills" / skill / "SKILL.md").exists():
            raise InstallError(f"missing skill {skill}")


def _ignore(_directory: str, names: list[str]) -> set[str]:
    return {name for name in names if name in EXCLUDED_NAMES or name.endswith(".egg-info")}


def _marketplace_entry() -> dict:
    return {
        "name": PLUGIN_NAME,
        "source": {"source": "local", "path": f"./plugins/{PLUGIN_NAME}"},
        "policy": {"installation": "AVAILABLE", "authentication": "ON_INSTALL"},
        "category": "Coding",
    }


def _load_or_seed_marketplace(path: Path) -> dict:
    if not path.exists():
        return {"name": "personal", "interface": {"displayName": "Personal"}, "plugins": []}
    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        raise InstallError(f"invalid marketplace.json: {exc}") from exc
    data.setdefault("name", "personal")
    data.setdefault("interface", {}).setdefault("displayName", "Personal")
    data.setdefault("plugins", [])
    if not isinstance(data["plugins"], list):
        raise InstallError("marketplace.json plugins must be a list")
    return data


def _upsert_plugin_entry(data: dict) -> None:
    entry = _marketplace_entry()
    plugins = data["plugins"]
    for index, existing in enumerate(plugins):
        if existing.get("name") == PLUGIN_NAME:
            plugins[index] = entry
            return
    plugins.append(entry)


def _home_from_marketplace_path(marketplace_path: Path) -> Path:
    if (
        marketplace_path.name == "marketplace.json"
        and marketplace_path.parent.name == "plugins"
        and marketplace_path.parent.parent.name == ".agents"
    ):
        return marketplace_path.parent.parent.parent
    return marketplace_path.parent


def install_plugin(
    *,
    source_root: Path,
    home: Path | None = None,
    marketplace_path: Path | None = None,
    yes: bool = False,
) -> InstallResult:
    source_root = _canonical_source_root(source_root.resolve())
    marketplace_path = marketplace_path.expanduser() if marketplace_path is not None else None
    home = (
        _home_from_marketplace_path(marketplace_path)
        if home is None and marketplace_path is not None
        else Path.home() if home is None else home
    )
    _validate_source(source_root)

    plugin_dir = home / "plugins" / PLUGIN_NAME
    marketplace_path = marketplace_path or home / ".agents" / "plugins" / "marketplace.json"

    if plugin_dir.exists():
        if not yes:
            raise InstallError(f"target plugin directory already exists: {plugin_dir}; pass --yes to replace")
        shutil.rmtree(plugin_dir)
    plugin_dir.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source_root, plugin_dir, ignore=_ignore)

    marketplace = _load_or_seed_marketplace(marketplace_path)
    _upsert_plugin_entry(marketplace)
    marketplace_path.parent.mkdir(parents=True, exist_ok=True)
    marketplace_path.write_text(json.dumps(marketplace, indent=2, ensure_ascii=False) + "\n")

    return InstallResult(
        plugin_dir=plugin_dir,
        marketplace_path=marketplace_path,
        next_steps=f"Run: codex plugin add {PLUGIN_NAME}@{marketplace['name']}\nThen enable Bug Fix Kit from Codex /plugins.",
    )
