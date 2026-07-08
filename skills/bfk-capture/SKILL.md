---
name: bfk-capture
description: "One-stop Bug Fix Kit capture: create an independent request capture or replay the current runner, then write request/response/log artifacts."
---

# Bug Fix Kit — Capture

Use when the user invokes `$bfk-capture [key=value ...]` or wants one-stop capture of reproducible evidence for a local bug.

## Boundary

- Creates a new independent capture only from the current request context: curl sample, base URL, endpoint, headers/body, log files, and supplied params.
- Keeps one active capture at `.bfk/`; before a new capture replaces it, archives existing current artifacts under `.bfk/archive/YYYY-MM-DD_HH-mm-ss/`.
- When invoked with no params and no new request context, replays the existing `.bfk/runner.py`.
- When params or partial context are provided but the request cannot be built, asks for the missing request context instead of reusing old state.
- Executes the selected local request once.
- Writes `.bfk/request.json`, `.bfk/response.json`, and `.bfk/output.log`.
- Archives and then clears stale current artifacts before writing the new capture, including `.bfk/root-cause.md`, `.bfk/fix-plan.md`, `.bfk/fix.md`, `.bfk/fix_output.log`, and `.bfk/probe.json` when present.
- Refuses to start a new capture while probe residue (`BFK-PROBE` lines) remains in application code; `bfk capture-run` reports the residue files and the user must run `$bfk-probe --revert` first.
- Does not manually create, archive, delete, or rewrite `.bfk` files outside the single `bfk capture-run` command.
- Does not locate root cause; does not analyze root cause.
- Does not edit code and does not modify application files.
- Does not write `root-cause.md`, `fix-plan.md`, or `fix.md`.

## Workflow

1. If the user provided no params and no new request context, replay through `bfk capture-run`; if `.bfk/runner.py` is missing, ask for a reproducible request.
2. If the user provided params or new context, build a new independent capture from the current request context only.
3. Execute the deterministic capture pipeline exactly once through the internal command `bfk capture-run` (creates or replays the runner, archives any previous completed capture evidence, snapshots log offsets, runs the request once, and writes the artifacts). Pass the gathered request context as arguments, for example:
   `bfk capture-run account=13900000000 --base-url http://127.0.0.1:8000 --endpoint "POST /login" --log-file logs/app.log`.
   Reuse `--request-sample`/`--request-sample-file` when the context is a curl sample, and omit params to replay the existing runner.
4. Inspect the command summary and current artifacts: `.bfk/request.json`, `.bfk/response.json`, and `.bfk/output.log`.
5. If the service, runner, request, or logs are blocked, still write every available artifact and summarize missing evidence in the Codex response.

## Output language

- Default to Chinese for user-facing summaries and missing-evidence descriptions.
- If the user explicitly asks for another language, follow that language for the current task.
- Preserve machine-readable values, file paths, code symbols, JSON keys, HTTP fields, and quoted logs/errors in their original form.
