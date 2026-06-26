# Bug Fix Kit

Bug Fix Kit (`bfk`) is a local Codex plugin for repeatable bug reproduction, diagnosis, and fix sessions.

It keeps the boring mechanics in a small stdlib Python helper CLI and leaves root-cause diagnosis/fix judgment to Codex skills.

## Install

For local development:

```bash
python3 -m pip install -e .
bfk install --yes
```

`bfk install` copies the plugin to `~/plugins/bug-fix-kit`, updates the personal marketplace file at `~/.agents/plugins/marketplace.json`, and prints the next `codex plugin add bug-fix-kit@personal` command. Then enable `Bug Fix Kit` from Codex `/plugins` and start a new Codex thread if skills are not immediately visible.

Advanced local install paths are explicit: `bfk install --plugin-root . --marketplace ~/.agents/plugins/marketplace.json --yes`. `--source-root` remains accepted as a compatibility alias for `--plugin-root`.

## Local helper CLI

```bash
bfk --help
bfk doctor
bfk init-project --base-url http://localhost:8000 --log-file logs/app.log
bfk new login_failed account=13900000000
bfk run
```

The helper CLI intentionally does **not** provide deterministic `bfk diagnose` or `bfk fix` commands. Those steps require Codex judgment and are exposed as skills.

## Codex workflow

```text
$bfk-init
$bfk-new <issue_name> <params>
$bfk-run [issue_id]
$bfk-diagnose [issue_id]
$bfk-fix [issue_id]
```

The loop writes evidence under `.bfk/`:

```text
.bfk/
├── PROJECT.md
└── issues/
    └── <issue_id>/
        ├── issue.md
        ├── runner.py
        └── iterations/
            └── 001/
                ├── request.json
                ├── response.json
                ├── output.log
                ├── diagnosis.md
                └── fix.md
```

## MVP boundaries

- `$bfk-run` executes and captures only; it does not diagnose or edit code.
- `$bfk-diagnose` writes `diagnosis.md` only; it does not edit code.
- `$bfk-fix` writes `fix.md` and may edit code only for clear code defects; it does not run verification.
- No PyPI release automation, demo HTTP app, Web UI, OpenTelemetry, remote logs, or auto-fix loop in MVP.
