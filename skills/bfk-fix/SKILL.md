---
name: bfk-fix
description: Apply a minimal code fix from the latest bfk diagnosis and write fix.md without running verification.
---

# Bug Fix Kit — Fix

Use when the user invokes `$bfk-fix [issue_id]`.

## Boundary

- Reads latest `diagnosis.md`.
- Writes current iteration `fix.md`.
- May modify local code only when `Problem Status` is `failed`, root cause is clear, related files are clear, and the issue is a code defect.
- Does not run `$bfk-run`.
- Does not run verification automatically.
- Refuses code edits for `passed`, `blocked`, `unknown`, unclear root cause, service-down, auth, local data, or dependency/mock environment problems.

## Workflow

1. Resolve the selected or latest issue and latest iteration.
2. Parse `Problem Status` from `diagnosis.md`.
3. If status is not `failed`, do not modify code; write `fix.md` explaining why.
4. If status is `failed`, make the smallest root-cause code change; do not refactor unrelated code or change public API contracts unless diagnosis requires it.
5. Write `fix.md` with diagnosis used, fix summary, changed files, details, risk, and next action.
6. Tell the user to run `$bfk-run` next to verify.
