from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DIST_PREFIX = "bug_fix_kit-"


def run(command: list[str], *, cwd: Path = REPO_ROOT) -> None:
    print("+ " + " ".join(command), flush=True)
    subprocess.run(command, cwd=cwd, text=True, check=True)


def clean_generated_artifacts() -> None:
    for path in [REPO_ROOT / "build", REPO_ROOT / "dist"]:
        if path.exists():
            shutil.rmtree(path)
    for path in REPO_ROOT.glob("*.egg-info"):
        if path.is_dir():
            shutil.rmtree(path)


def bin_path(venv_dir: Path, executable: str) -> Path:
    scripts = "Scripts" if os.name == "nt" else "bin"
    suffix = ".exe" if os.name == "nt" and executable in {"python", "pip", "bfk"} else ""
    return venv_dir / scripts / f"{executable}{suffix}"


def build_distributions(temp_dir: Path) -> list[Path]:
    dist_dir = temp_dir / "dist"
    dist_dir.mkdir()
    run([sys.executable, "-m", "build", "--no-isolation", "--sdist", "--wheel", "--outdir", str(dist_dir)])
    artifacts = sorted(dist_dir.iterdir())
    if not any(path.name.startswith(DIST_PREFIX) and path.suffix == ".whl" for path in artifacts):
        raise AssertionError(f"missing normalized wheel: {[p.name for p in artifacts]}")
    if not any(path.name.startswith("bug_fix_kit-") and path.name.endswith(".tar.gz") for path in artifacts):
        raise AssertionError(f"missing sdist: {[p.name for p in artifacts]}")
    run([sys.executable, "-m", "twine", "check", *map(str, artifacts)])
    return artifacts


def create_venv(venv_dir: Path) -> Path:
    import venv

    venv.EnvBuilder(with_pip=True).create(venv_dir)
    return bin_path(venv_dir, "python")


def install_wheel(python_bin: Path, artifacts: list[Path]) -> None:
    wheels = [path for path in artifacts if path.suffix == ".whl"]
    if len(wheels) != 1:
        raise AssertionError(f"expected one wheel, found {[p.name for p in wheels]}")
    run([str(python_bin), "-m", "pip", "install", str(wheels[0])])


def run_installed_smoke(python_bin: Path, work_dir: Path) -> None:
    venv_dir = python_bin.parents[1]
    bfk = bin_path(venv_dir, "bfk")
    home = work_dir / "home"
    marketplace = home / ".agents" / "plugins" / "marketplace.json"
    run([str(bfk), "--help"], cwd=work_dir)
    run([str(bfk), "doctor"], cwd=work_dir)
    run([str(bfk), "install", "--home", str(home), "--marketplace", str(marketplace), "--yes"], cwd=work_dir)
    plugin_dir = home / "plugins" / "bug-fix-kit"
    if not (plugin_dir / ".codex-plugin" / "plugin.json").exists():
        raise AssertionError("installed plugin manifest missing")
    if not (plugin_dir / "skills" / "bfk-run" / "SKILL.md").exists():
        raise AssertionError("installed plugin skills missing")
    data = json.loads(marketplace.read_text())
    if not any(plugin.get("name") == "bug-fix-kit" for plugin in data.get("plugins", [])):
        raise AssertionError("marketplace entry missing")


def main() -> int:
    clean_generated_artifacts()
    try:
        run([sys.executable, "-m", "pytest", "-q"])
        run([sys.executable, "-m", "compileall", "-q", "bug_fix_kit", "tests"])
        with tempfile.TemporaryDirectory(prefix="bug-fix-kit-release-") as tmp:
            temp_dir = Path(tmp)
            artifacts = build_distributions(temp_dir)
            python_bin = create_venv(temp_dir / "venv")
            install_wheel(python_bin, artifacts)
            work_dir = temp_dir / "smoke"
            work_dir.mkdir()
            run_installed_smoke(python_bin, work_dir)
    finally:
        clean_generated_artifacts()
    print("release-check: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
