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
   bfk run [issue_id]
   ```

3. Read the command output and inspect the new iteration path.
4. If `response.json.transport_error` is present, report that the run captured an environment/transport failure; leave analysis to `$bfk-diagnose`.
5. Recommend `$bfk-diagnose` next.
