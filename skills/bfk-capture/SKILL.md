---
name: bfk-capture
description: "One-stop Bug Fix Kit capture: create/reuse the current local capture, execute the request, and write request/response/log artifacts."
---

# Bug Fix Kit — Capture

Use when the user invokes `$bfk-capture "<issue>" [key=value ...]` or wants one-stop capture of reproducible evidence for a local bug.

## Boundary

- Creates or reuses only the local BFK project state needed to replay the current issue.
- May create or update `.bfk/PROJECT.md`, `.bfk/issue.md`, and `.bfk/runner.py` when they are missing.
- Replaces the current single capture at `.bfk/`; Bug Fix Kit does not track multiple active issues.
- Executes the selected local request once.
- Writes `.bfk/request.json`, `.bfk/response.json`, and `.bfk/output.log`.
- Deletes stale `.bfk/root-cause.md` and `.bfk/fix.md` before writing the new capture.
- Does not locate root cause; does not analyze root cause.
- Does not edit code and does not modify application files.
- Does not write `root-cause.md` or `fix.md`.

## Workflow

1. Resolve existing `.bfk/PROJECT.md` knowledge or create the minimum project knowledge from the issue, request sample, base URL, headers, log files, and supplied params.
2. Replace the current capture files under `.bfk/`, preserving `.bfk/PROJECT.md`.
3. Generate the smallest `.bfk/runner.py` from the saved request sample or request parameters.
4. Execute the runner through deterministic BFK mechanics.
5. Capture the exact request, response, and new log output into `.bfk/request.json`, `.bfk/response.json`, and `.bfk/output.log`.
6. If the service, runner, request, or logs are blocked, still write every available artifact and summarize missing evidence in the Codex response.
