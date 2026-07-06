# Release Checklist

This checklist is the release gate for publishing the PyPI distribution `bug-fix-kit`.
The installed console script is `bfk`; the import package is `bug_fix_kit`.

## Release Identity

- PyPI distribution: `bug-fix-kit`
- Console script: `bfk`
- Import package: `bug_fix_kit`
- Plugin name: `bug-fix-kit`

Before upload, re-check official PyPI version availability. If the target version is unavailable, stop; do not rename or bump silently.

## Supported Surface

The release covers the local-first plugin shell:

- `bfk --help`
- `bfk doctor`
- `bfk install --yes`
- packaged `.codex-plugin/plugin.json` via generated `bug_fix_kit/plugin_payload/bug-fix-kit`
- packaged `$bfk-capture`, `$bfk-locate`, `$bfk-fix-plan`, and `$bfk-fix` skill surfaces
- `root-cause.md` as the locate report artifact

`pip install bug-fix-kit` must not automatically enable a Codex plugin. The supported path remains `pip install bug-fix-kit`, then `bfk install --yes`, then manual Codex plugin enable instructions.

## Deferred / Non-Goals

- no package rename
- no forced TestPyPI gate
- no automatic Codex plugin activation
- no public workflow CLI commands
- no UI, demo HTTP app, remote logging, observability, or automatic mock system

## Local Release Gate

```bash
python -m pip install -e '.[release]'
python scripts/check-release.py
```

The script verifies:

1. `python -m pytest -q`
2. `python -m compileall -q src/bug_fix_kit scripts tests`
3. `src/bug_fix_kit`, sdist and wheel build with isolated Hatch/PEP 517 build
4. archive inspection for generated `bug_fix_kit/plugin_payload/bug-fix-kit` and all required skills
5. `twine check`
6. wheel install into a fresh virtual environment
7. sdist install into a fresh virtual environment
8. installed `bfk --help`
9. installed `bfk doctor`
10. installed `bfk install --yes` against a temp home, including plugin files and marketplace entry

Do not publish if this gate fails.

## Official PyPI Publish

Dry-run:

```bash
python scripts/publish-release.py
```

Publish only when the release gate passes and PyPI credentials are available:

```bash
python scripts/publish-release.py --publish
```

After upload, verify from a clean environment:

```bash
python -m venv /tmp/bug-fix-kit-pypi
/tmp/bug-fix-kit-pypi/bin/python -m pip install bug-fix-kit
/tmp/bug-fix-kit-pypi/bin/bfk --help
/tmp/bug-fix-kit-pypi/bin/bfk doctor
/tmp/bug-fix-kit-pypi/bin/bfk install --home /tmp/bug-fix-kit-home --yes
```

If credentials are missing or PyPI rejects the upload, stop with the exact pending command and evidence.
