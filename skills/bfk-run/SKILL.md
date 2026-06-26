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
2. Prefer the helper command:

   ```bash
   bfk run [issue_id] [--timeout seconds]
   ```

3. Read the command output and inspect the new iteration path.
4. Interpret `response.json` mechanically only:
   - `transport_error: null` means an HTTP response was captured, including possible 4xx/5xx business failures.
   - `transport_error.type: transport_error` means request construction/network/HTTP transport failed.
   - `transport_error.type: runner_error` means runner import/config/build failed, but durable artifacts were still written.
5. If `output.log` contains a missing/truncated log note, report that evidence explicitly and leave root-cause analysis to `$bfk-diagnose`.
6. Recommend `$bfk-diagnose` next.
