---
name: bfk-new
description: Create one bfk issue session and issue-level runner.py without executing it.
---

# Bug Fix Kit — New Issue

Use when the user invokes `$bfk-new <issue_name> <params>`.

## Boundary

- Reads `.bfk/PROJECT.md`.
- Creates `.bfk/issues/<issue_id>/issue.md`.
- Creates `.bfk/issues/<issue_id>/runner.py`.
- Creates `.bfk/issues/<issue_id>/iterations/`.
- Does not run requests.
- Does not diagnose.
- Does not fix code.

## Workflow

1. Confirm `.bfk/PROJECT.md` exists; if missing, tell the user to run `$bfk-init`.
2. Prefer the helper command:

   ```bash
   bfk new <issue_name> [key=value ...]
   ```

3. Preserve `key=value` params exactly. Free-form positional params become a single `value` param when no explicit `value=` is supplied.
4. Do not infer endpoint-specific fields such as passwords or user IDs. If the request needs custom shape, edit the generated `runner.py` before `$bfk-run`.
5. Report the issue directory and recommend `$bfk-run` next.
