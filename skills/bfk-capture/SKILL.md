---
name: bfk-capture
description: "One-stop Bug Fix Kit capture: create/reuse local issue context, execute the request, and write request/response/log artifacts."
---

# Bug Fix Kit — Capture

Use when the user invokes `$bfk-capture "<issue>" [key=value ...]` or wants one-stop capture of reproducible evidence for a local bug.

## Boundary

- Creates or reuses only the local BFK project/session state needed to replay the issue.
- May create or update `.bfk/PROJECT.md`, `.bfk/issues/<issue_id>/issue.md`, and `runner.py` when they are missing.
- May reuse an existing issue/runner when the user supplies an issue id.
- Executes the selected local request once and writes the next numbered iteration.
- Writes `request.json`, `response.json`, `output.log`, and a concise `capture.md` summary.
- Does not locate root cause; does not analyze root cause.
- Does not edit code and does not modify application files.
- Does not write `root-cause.md` or `fix.md`.

## Workflow

1. Resolve existing `.bfk/PROJECT.md` knowledge or create the minimum project knowledge from the issue, request sample, base URL, headers, log files, and supplied params.
2. Resolve or create the issue/session under `.bfk/issues/<issue_id>/`.
3. Reuse the issue runner when present; otherwise generate the smallest `runner.py` from the saved request sample or request parameters.
4. Execute the runner through deterministic BFK mechanics.
5. Capture the exact request, response, and new log output into `iterations/<nnn>/request.json`, `response.json`, and `output.log`.
6. Write `capture.md` with issue id, iteration path, request summary, response/transport status, log capture status, and the next step: `$bfk-locate`.
7. If the service, runner, request, or logs are blocked, still write the available artifacts and describe missing evidence in `capture.md`.
