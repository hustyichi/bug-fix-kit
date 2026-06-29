---
name: bfk-capture
description: "One-stop Bug Fix Kit capture: create an independent request capture or replay the current runner, then write request/response/log artifacts."
---

# Bug Fix Kit — Capture

Use when the user invokes `$bfk-capture [key=value ...]` or wants one-stop capture of reproducible evidence for a local bug.

## Boundary

- Creates a new independent capture only from the current request context: curl sample, base URL, endpoint, headers/body, log files, and supplied params.
- Does not create or reuse `.bfk/PROJECT.md` or `.bfk/issue.md`.
- Replaces the current single capture at `.bfk/`; Bug Fix Kit does not track multiple active captures.
- When invoked with no params and no new request context, replays the existing `.bfk/runner.py`.
- When params or partial context are provided but the request cannot be built, asks for the missing request context instead of reusing old state.
- Executes the selected local request once.
- Writes `.bfk/request.json`, `.bfk/response.json`, and `.bfk/output.log`.
- Deletes stale `.bfk/root-cause.md`, `.bfk/fix.md`, and `.bfk/fix_output.log` before writing the new capture.
- Does not locate root cause; does not analyze root cause.
- Does not edit code and does not modify application files.
- Does not write `root-cause.md` or `fix.md`.

## Workflow

1. If the user provided no params and no new request context, load existing `.bfk/runner.py` for replay; if it is missing, ask for a reproducible request.
2. If the user provided params or new context, build a new independent capture from the current request context only.
3. Replace the current capture files under `.bfk/`.
4. Generate the smallest `.bfk/runner.py` from the current request sample or request parameters.
5. Execute the runner through deterministic BFK mechanics.
6. Capture the exact request, response, and new log output into `.bfk/request.json`, `.bfk/response.json`, and `.bfk/output.log`.
7. If the service, runner, request, or logs are blocked, still write every available artifact and summarize missing evidence in the Codex response.

## Output language

- Default to Chinese for user-facing summaries and missing-evidence descriptions.
- If the user explicitly asks for another language, follow that language for the current task.
- Preserve machine-readable values, file paths, code symbols, JSON keys, HTTP fields, and quoted logs/errors in their original form.
