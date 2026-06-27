# Release Checklist

This checklist is the release gate for publishing the PyPI distribution `bug-fix-kit`.
The installed console script is `bfk`; the import package is `bug_fix_kit`.

## Release identity

- PyPI distribution: `bug-fix-kit`
- Console script: `bfk`
- Import package: `bug_fix_kit`
- Plugin name: `bug-fix-kit`

Before upload, re-check official PyPI name/version availability. If the name or version is unavailable, stop; do not rename or bump silently.

## Supported surface

The release covers the existing local-first plugin shell:

- `bfk --help`
- `bfk doctor`
- `bfk install --yes`
- packaged `.codex-plugin/plugin.json`
- packaged `skills/bfk-*` skill surfaces

`pip install bug-fix-kit` must not automatically enable a Codex plugin. The supported path remains `pip install bug-fix-kit`, then `bfk install --yes`, then manual Codex plugin enable instructions.

## Deferred / non-goals

- no new BFK workflow features
- no package rename
- no forced TestPyPI gate
- no automatic Codex plugin activation
- no UI, demo HTTP app, remote logging, observability, or auto-fix loop

## Local release gate

```bash
python scripts/check-release.py
```

The script verifies:

1. `python -m pytest -q`
2. `python -m compileall -q bug_fix_kit tests`
3. sdist and wheel build
4. `twine check`
5. wheel install into a fresh virtual environment
6. installed `bfk --help`
7. installed `bfk doctor`
8. installed `bfk install --yes` against a temp home, including plugin files and marketplace entry

Do not publish if this gate fails.

## Official PyPI publish

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
