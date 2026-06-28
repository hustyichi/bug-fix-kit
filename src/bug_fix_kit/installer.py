from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from importlib import resources
from importlib.resources.abc import Traversable
from pathlib import Path
from typing import BinaryIO

from .contract import REQUIRED_SKILLS

PLUGIN_NAME = "bug-fix-kit"
PAYLOAD_DIR = "plugin_payload"
DEV_PAYLOAD_NAMES = (".codex-plugin", "skills")
EXCLUDED_NAMES = {
    ".git",
    ".omx",
    ".bfk",
    ".venv",
    "__pycache__",
    ".pytest_cache",
    "build",
    "dist",
}


class InstallError(RuntimeError):
    pass


@dataclass(frozen=True)
class InstallResult:
    plugin_dir: Path
    marketplace_path: Path
    next_steps: str


@dataclass(frozen=True)
class PayloadSource:
    kind: str
    root: Path | Traversable
    display_root: str
    names: tuple[str, ...] | None = None


def _node(root: Path | Traversable, *parts: str) -> Path | Traversable:
    current: Path | Traversable = root
    for part in parts:
        current = current / part if isinstance(current, Path) else current.joinpath(part)
    return current


def _exists(node: Path | Traversable) -> bool:
    if isinstance(node, Path):
        return node.exists()
    return node.is_file() or node.is_dir()


def _is_dir(node: Path | Traversable) -> bool:
    return node.is_dir()


def _read_text(node: Path | Traversable) -> str:
    if isinstance(node, Path):
        return node.read_text()
    return node.read_text()


def _open_binary(node: Path | Traversable) -> BinaryIO:
    return node.open("rb")


def _repo_root_from_package() -> Path:
    return Path(__file__).resolve().parents[2]


def _has_payload(root: Path | Traversable) -> bool:
    return _exists(_node(root, ".codex-plugin", "plugin.json")) and _is_dir(_node(root, "skills"))


def _packaged_payload_root() -> Traversable:
    return resources.files("bug_fix_kit").joinpath(PAYLOAD_DIR, PLUGIN_NAME)


def resolve_payload_source(source_root: Path | None = None) -> PayloadSource:
    if source_root is not None:
        explicit = source_root.expanduser().resolve()
        candidate = explicit
        if _exists(_node(candidate, ".codex-plugin", "plugin.json")) or _is_dir(_node(candidate, "skills")):
            return PayloadSource("explicit", candidate, str(candidate), DEV_PAYLOAD_NAMES)
        raise InstallError(f"missing plugin.json at {candidate / '.codex-plugin' / 'plugin.json'}")

    repo_root = _repo_root_from_package()
    if _has_payload(repo_root):
        return PayloadSource("dev-root", repo_root, str(repo_root), DEV_PAYLOAD_NAMES)

    packaged = _packaged_payload_root()
    if _has_payload(packaged):
        return PayloadSource("package-resource", packaged, f"bug_fix_kit/{PAYLOAD_DIR}/{PLUGIN_NAME}", None)

    raise InstallError("could not locate Bug Fix Kit plugin payload")


def _validate_payload(payload: PayloadSource) -> None:
    manifest_node = _node(payload.root, ".codex-plugin", "plugin.json")
    if not _exists(manifest_node):
        raise InstallError(f"missing plugin.json at {payload.display_root}/.codex-plugin/plugin.json")
    try:
        manifest = json.loads(_read_text(manifest_node))
    except json.JSONDecodeError as exc:
        raise InstallError(f"invalid plugin.json: {exc}") from exc
    if manifest.get("name") != PLUGIN_NAME:
        raise InstallError(f"plugin.json name must be {PLUGIN_NAME!r}")
    for skill in REQUIRED_SKILLS:
        if not _exists(_node(payload.root, "skills", skill, "SKILL.md")):
            raise InstallError(f"missing skill {skill}")


def _excluded(name: str) -> bool:
    return name in EXCLUDED_NAMES or name.endswith(".egg-info")


def _copy_tree(src: Path | Traversable, dest: Path) -> None:
    name = src.name
    if _excluded(name):
        return
    if src.is_dir():
        dest.mkdir(parents=True, exist_ok=True)
        for child in src.iterdir():
            _copy_tree(child, dest / child.name)
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    with _open_binary(src) as reader, dest.open("wb") as writer:
        shutil.copyfileobj(reader, writer)


def _copy_payload(payload: PayloadSource, plugin_dir: Path) -> None:
    names = payload.names or tuple(child.name for child in payload.root.iterdir() if not _excluded(child.name))
    for name in names:
        _copy_tree(_node(payload.root, name), plugin_dir / name)


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
    source_root: Path | None = None,
    home: Path | None = None,
    marketplace_path: Path | None = None,
    yes: bool = False,
) -> InstallResult:
    payload = resolve_payload_source(source_root)
    _validate_payload(payload)
    marketplace_path = marketplace_path.expanduser() if marketplace_path is not None else None
    home = (
        _home_from_marketplace_path(marketplace_path)
        if home is None and marketplace_path is not None
        else Path.home() if home is None else home.expanduser()
    )

    plugin_dir = home / "plugins" / PLUGIN_NAME
    marketplace_path = marketplace_path or home / ".agents" / "plugins" / "marketplace.json"

    if plugin_dir.exists():
        if not yes:
            raise InstallError(f"target plugin directory already exists: {plugin_dir}; pass --yes to replace")
        shutil.rmtree(plugin_dir)
    plugin_dir.mkdir(parents=True, exist_ok=True)
    _copy_payload(payload, plugin_dir)

    marketplace = _load_or_seed_marketplace(marketplace_path)
    _upsert_plugin_entry(marketplace)
    marketplace_path.parent.mkdir(parents=True, exist_ok=True)
    marketplace_path.write_text(json.dumps(marketplace, indent=2, ensure_ascii=False) + "\n")

    return InstallResult(
        plugin_dir=plugin_dir,
        marketplace_path=marketplace_path,
        next_steps=f"Run: codex plugin add {PLUGIN_NAME}@{marketplace['name']}\nThen enable Bug Fix Kit from Codex /plugins.",
    )
