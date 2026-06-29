# Bug Fix Kit

Language: [简体中文](README.md) | English

Bug Fix Kit (`bfk`) is a PyPI-distributed local Codex plugin that compresses local service bug work into three steps: capture evidence, locate the root cause, and apply the smallest fix.

It keeps deterministic request replay, log capture, and artifact writing in a small stdlib Python helper, while Codex skills handle root-cause judgment and code repair.

## Install

Release install:

```bash
python3 -m pip install bug-fix-kit
bfk --help
bfk doctor
bfk install --yes
```

`pip install bug-fix-kit` installs only the `bfk` CLI; it does not automatically enable a Codex plugin.

`bfk install` copies the plugin to `~/plugins/bug-fix-kit`, updates `~/.agents/plugins/marketplace.json`, and prints the next `codex plugin add bug-fix-kit@personal` command. Then enable `Bug Fix Kit` from Codex `/plugins`; start a new Codex thread if skills are not immediately visible.

Local development install:

```bash
python3 -m pip install -e .
bfk install --yes
```

`--plugin-root` / `--source-root` may point at a custom plugin source; when it points at this repository root, `bfk` copies only `.codex-plugin/` and `skills/`. From an installed wheel, `bfk` uses the generated `bug_fix_kit/plugin_payload/bug-fix-kit` package resource. Existing installed plugin directories are overwritten only with `--yes`.

The PyPI distribution is `bug-fix-kit`, the console script is `bfk`, and the Python import package is `bug_fix_kit`.

## Local Helper CLI

```bash
bfk --help
bfk doctor
bfk install --yes
```

The helper CLI is only for plugin installation and shell checks. Bug handling is done by Codex skills; the CLI does not expose workflow commands.

## Codex Workflow

```text
$bfk-capture <full request context and optional key=value params>
$bfk-locate
$bfk-fix
```

Direct log location also uses locate:

```text
$bfk-locate --log logs/error.log --issue "login failed"
```

The active bug evidence lives under `.bfk/`; previous bug evidence is archived below `.bfk/archive/`:

```text
.bfk/
├── runner.py
├── request.json
├── response.json
├── output.log
├── root-cause.md
├── fix.md
├── fix_output.log
└── archive/
    └── 2026-06-29_13-30-12/
        ├── runner.py
        ├── request.json
        ├── response.json
        ├── output.log
        ├── root-cause.md
        ├── fix.md
        └── fix_output.log
```

## Mechanics

### Capture

`$bfk-capture` is the one-stop evidence entrypoint. From the current request context, request sample, and request params, it archives the previous current evidence under `.bfk/archive/YYYY-MM-DD_HH-mm-ss/`, replaces the current evidence under `.bfk/`, generates `runner.py`, executes one local request, and captures request, response, and new logs.

Bug Fix Kit does not keep reusable project-level request config. Provide the curl sample, base URL, headers/body, log files, and any request params in the same `$bfk-capture` invocation. Supplying only new params does not partially override the previous capture. Invoking `$bfk-capture` with no params and no new context replays the existing `.bfk/runner.py`.

Boundary: executes and captures only; it does not locate root cause, edit code, or write `root-cause.md`. A new capture archives stale current artifacts before clearing `root-cause.md`, `fix.md`, and `fix_output.log`; replaying the current `.bfk/runner.py` with no new context does not create an archive.

### Locate

`$bfk-locate` reads capture artifacts or explicit log files plus related code. It writes `root-cause.md` by tracing the direct chain from symptom to log/response evidence to code path to root cause.

If evidence is insufficient, it reports `unknown` with missing evidence. If service, logs, inputs, or code context are unavailable, it reports `blocked`. It must not treat the final exception as the confirmed root cause by itself.

Boundary: analyzes and writes the root-cause report only; it does not execute requests, edit code, or write `fix.md`.

### Fix

`$bfk-fix` applies the smallest code repair only when `root-cause.md` confirms a code defect. When reproducible capture context exists, it should reuse the current request under `.bfk/` for verification, write the verification log to `.bfk/fix_output.log`, and leave the original failure log `.bfk/output.log` intact. For log-only cases, it writes `changed_unverified` and tells the user what request or manual check is needed.

Boundary: it does not guess fixes from `unknown` / `blocked` reports and does not claim verification it did not run.

## Output Language

User-facing BFK descriptions default to Chinese, including capture summaries, `root-cause.md`, and `fix.md`. If the user explicitly requests another language, follow that intent. Keep status values, field names, file paths, code symbols, JSON keys, HTTP fields, and quoted logs unchanged.

## MVP Boundaries

- No runtime dependencies.
- No demo HTTP app, Web UI, OpenTelemetry, remote logging, YAML config, or automatic mocks.
- No public workflow CLI commands.
