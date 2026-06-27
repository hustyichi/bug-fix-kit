---
name: bfk-diagnose
description: Analyze the latest bfk iteration evidence and write diagnosis.md without editing code.
---

# Bug Fix Kit — Diagnose

Use when the user invokes `$bfk-diagnose [issue_id]`.

## Boundary

- Reads `.bfk/PROJECT.md`, `issue.md`, current `request.json`, `response.json`, and `output.log`.
- Reads previous `diagnosis.md` and `fix.md` when present.
- Writes only the current iteration `diagnosis.md`.
- Does not modify code.
- Does not run requests.
- Does not write `fix.md`.

## Workflow

1. Resolve the selected or latest issue and latest iteration.
2. If `response.json` has `transport_error`, set `Problem Status: blocked`; this is not an automatic code-fix case.
3. Otherwise inspect response, logs, and related local code to identify current status: `failed`, `passed`, `blocked`, or `unknown`.
4. Write Markdown `diagnosis.md` with execution summary, Problem Status, root cause, evidence, related files, suggested fix, and next action.
5. Recommend `$bfk-fix` only when status is `failed` and evidence supports a code defect. For runner/service/log/auth/environment blockers, tell the user what to restore and then rerun `$bfk-run`.
