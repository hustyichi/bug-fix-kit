from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import zipfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DIST_PREFIX = "bug_fix_kit-"
REQUIRED_SKILLS = ("bfk-init", "bfk-new", "bfk-run", "bfk-diagnose", "bfk-fix")
WHEEL_PAYLOAD_PREFIX = "bug_fix_kit/plugin_payload/bug-fix-kit"


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
    for path in REPO_ROOT.glob("src/*.egg-info"):
        if path.is_dir():
            shutil.rmtree(path)


def bin_path(venv_dir: Path, executable: str) -> Path:
    scripts = "Scripts" if os.name == "nt" else "bin"
    suffix = ".exe" if os.name == "nt" and executable in {"python", "pip", "bfk"} else ""
    return venv_dir / scripts / f"{executable}{suffix}"


def build_distributions(temp_dir: Path) -> list[Path]:
    dist_dir = temp_dir / "dist"
    dist_dir.mkdir()
    run([sys.executable, "-m", "build", "--sdist", "--wheel", "--outdir", str(dist_dir)])
    artifacts = sorted(dist_dir.iterdir())
    if not any(path.name.startswith(DIST_PREFIX) and path.suffix == ".whl" for path in artifacts):
        raise AssertionError(f"missing normalized wheel: {[p.name for p in artifacts]}")
    if not any(path.name.startswith("bug_fix_kit-") and path.name.endswith(".tar.gz") for path in artifacts):
        raise AssertionError(f"missing sdist: {[p.name for p in artifacts]}")
    inspect_archives(artifacts)
    run([sys.executable, "-m", "twine", "check", *map(str, artifacts)])
    return artifacts


def inspect_archives(artifacts: list[Path]) -> None:
    wheel = next(path for path in artifacts if path.suffix == ".whl")
    sdist = next(path for path in artifacts if path.name.endswith(".tar.gz"))
    with zipfile.ZipFile(wheel) as archive:
        names = set(archive.namelist())
    _assert_contains(names, f"{WHEEL_PAYLOAD_PREFIX}/.codex-plugin/plugin.json", wheel.name)
    for skill in REQUIRED_SKILLS:
        _assert_contains(names, f"{WHEEL_PAYLOAD_PREFIX}/skills/{skill}/SKILL.md", wheel.name)
    if any(name.startswith("bug_fix_kit/plugin/") for name in names):
        raise AssertionError("wheel contains removed bug_fix_kit/plugin duplicate")

    with tarfile.open(sdist, "r:gz") as archive:
        names = {member.name for member in archive.getmembers()}
    _assert_sdist_contains(names, ".codex-plugin/plugin.json", sdist.name)
    for skill in REQUIRED_SKILLS:
        _assert_sdist_contains(names, f"skills/{skill}/SKILL.md", sdist.name)
    _assert_sdist_contains(names, "src/bug_fix_kit/installer.py", sdist.name)


def _assert_contains(names: set[str], expected: str, archive: str) -> None:
    if expected not in names:
        raise AssertionError(f"{archive} missing {expected}")


def _assert_sdist_contains(names: set[str], expected_suffix: str, archive: str) -> None:
    if not any(name.endswith("/" + expected_suffix) for name in names):
        raise AssertionError(f"{archive} missing {expected_suffix}")


def create_venv(venv_dir: Path) -> Path:
    import venv

    try:
        venv.EnvBuilder(with_pip=True).create(venv_dir)
    except subprocess.CalledProcessError:
        uv = shutil.which("uv")
        if uv is None:
            raise
        if venv_dir.exists():
            shutil.rmtree(venv_dir)
        run([uv, "venv", "--python", sys.executable, str(venv_dir)])
    return bin_path(venv_dir, "python")


def install_artifact(python_bin: Path, artifact: Path) -> None:
    command = [str(python_bin), "-m", "pip", "install", str(artifact)]
    print("+ " + " ".join(command), flush=True)
    try:
        subprocess.run(command, cwd=REPO_ROOT, text=True, check=True)
    except subprocess.CalledProcessError:
        uv = shutil.which("uv")
        if uv is None:
            raise
        run([uv, "pip", "install", "--python", str(python_bin), str(artifact)])


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
    for skill in REQUIRED_SKILLS:
        if not (plugin_dir / "skills" / skill / "SKILL.md").exists():
            raise AssertionError(f"installed plugin skill missing: {skill}")
    data = json.loads(marketplace.read_text())
    if not any(plugin.get("name") == "bug-fix-kit" for plugin in data.get("plugins", [])):
        raise AssertionError("marketplace entry missing")


def smoke_artifact(artifact: Path, work_dir: Path) -> None:
    python_bin = create_venv(work_dir / "venv")
    install_artifact(python_bin, artifact)
    smoke_dir = work_dir / "smoke"
    smoke_dir.mkdir()
    run_installed_smoke(python_bin, smoke_dir)


def main() -> int:
    clean_generated_artifacts()
    try:
        run([sys.executable, "-m", "pytest", "-q"])
        run([sys.executable, "-m", "compileall", "-q", "src/bug_fix_kit", "scripts", "tests"])
        with tempfile.TemporaryDirectory(prefix="bug-fix-kit-release-") as tmp:
            temp_dir = Path(tmp)
            artifacts = build_distributions(temp_dir)
            wheel = next(path for path in artifacts if path.suffix == ".whl")
            sdist = next(path for path in artifacts if path.name.endswith(".tar.gz"))
            smoke_artifact(wheel, temp_dir / "wheel-smoke")
            smoke_artifact(sdist, temp_dir / "sdist-smoke")
    finally:
        clean_generated_artifacts()
    print("release-check: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
