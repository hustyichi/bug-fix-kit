---
name: bfk-run
description: Execute the current bfk issue runner and collect request, response, and logs for one iteration.
---

# Bug Fix Kit — Run

Use when the user invokes `$bfk-run [issue_id]`.

## Boundary

- Executes the selected issue `runner.py` through bfk mechanics.
- Writes `request.json`, `response.json`, and `output.log` in a new numbered iteration.
- Does not diagnose.
- Does not modify code.
- Does not write `diagnosis.md` or `fix.md`.

## Workflow

1. Resolve the specified issue or latest issue.
2. Execute the selected issue `runner.py` through local Python mechanics or equivalent direct Codex code. Do not invoke `bfk run`; the CLI is for plugin management, not the core Codex workflow.
3. Capture request, response, and logs into the next numbered `iterations/<nnn>/` directory.
4. Inspect the new iteration path.
5. Interpret `response.json` mechanically only:
   - `transport_error: null` means an HTTP response was captured, including possible 4xx/5xx business failures.
   - `transport_error.type: transport_error` means request construction/network/HTTP transport failed.
   - `transport_error.type: runner_error` means runner import/config/build failed, but durable artifacts were still written.
6. If `output.log` contains a missing/truncated log note, report that evidence explicitly and leave root-cause analysis to `$bfk-diagnose`.
7. Recommend `$bfk-diagnose` next.
