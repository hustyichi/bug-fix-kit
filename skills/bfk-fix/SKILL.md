---
name: bfk-fix
description: "Apply the smallest code repair from a confirmed BFK root-cause.md and write fix.md with conditional verification."
---

# Bug Fix Kit — Fix

Use when the user invokes `$bfk-fix` after `$bfk-locate` has written a confirmed `.bfk/root-cause.md`.

## Boundary

- Reads `.bfk/root-cause.md` and related code files.
- Refuses to edit when `root-cause.md` is `unknown`, `blocked`, missing, or lacks a confirmed code defect.
- May modify local code only for a confirmed root cause with direct-chain evidence.
- Makes the smallest root-cause fix; no unrelated refactors or public API changes unless required by the confirmed defect.
- Does not guess fixes from incomplete, unknown, or blocked root-cause reports.
- Writes `.bfk/fix.md`.
- Verifies only when reproducible capture context exists.
- Does not claim verification for log-only cases or missing request context.

## Workflow

1. Read `.bfk/root-cause.md`.
2. If status is `unknown` or `blocked`, refuse code edits and write `fix.md` with status `refused` or `blocked`.
3. If status is not a confirmed code defect, refuse broad or guessed fixes.
4. Apply the smallest code change that addresses the confirmed root cause.
5. If `request.json`, `runner.py`, and required local service/log context exist, rerun the same capture path and inspect the result.
6. Write `fix.md` with root cause used, changed files, verification evidence, risk, and next action.

## Final statuses

- `fixed_verified`: code changed and reproducible capture passed.
- `changed_unverified`: code changed, but no reproducible capture context was available.
- `still_failed`: code changed, but rerun capture still fails.
- `refused`: no confirmed code defect or root cause is `unknown`.
- `blocked`: required files, service, logs, or permissions are unavailable.
