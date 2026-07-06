---
name: bfk-fix
description: "Apply the smallest code repair, preferring fix-plan.md when present, and write fix.md with conditional verification."
---

# Bug Fix Kit — Fix

Use when the user invokes `$bfk-fix` after `$bfk-locate` has written a confirmed `.bfk/root-cause.md`. If `.bfk/fix-plan.md` exists, treat it as the primary repair instructions.

## Boundary

- Reads `.bfk/root-cause.md`, `.bfk/fix-plan.md` when present, and related code files.
- Refuses to edit when `root-cause.md` is `unknown`, `blocked`, missing, or lacks a confirmed code defect.
- May modify local code only for a confirmed root cause with direct-chain evidence.
- When `.bfk/fix-plan.md` exists, follows that plan's proposed fix, files, constraints, rejected options, and verification plan before deriving a fallback from `root-cause.md`.
- Does not silently ignore `.bfk/fix-plan.md`; if the plan is stale, unsafe, too broad, or conflicts with the confirmed root cause, stop and write `fix.md` with `refused` or `blocked` and the reason.
- Makes the smallest root-cause fix; no unrelated refactors or public API changes unless required by the confirmed defect.
- Does not guess fixes from incomplete, unknown, or blocked root-cause reports.
- Writes `.bfk/fix.md`.
- When verification reruns the current capture, writes the new verification log to `.bfk/fix_output.log` and must not overwrite `.bfk/output.log`.
- Verifies only when reproducible capture context exists.
- Does not claim verification for log-only cases or missing request context.

## Workflow

1. Read `.bfk/root-cause.md`.
2. If status is `unknown` or `blocked`, refuse code edits and write `fix.md` with status `refused` or `blocked`.
3. If status is not a confirmed code defect, refuse broad or guessed fixes.
4. If `.bfk/fix-plan.md` exists, read it and apply the smallest code change that follows the current plan while still addressing the confirmed root cause.
5. If `.bfk/fix-plan.md` is absent, apply the smallest code change derived directly from the confirmed root cause.
6. If `request.json`, `runner.py`, and required local service/log context exist, rerun the same capture path through the internal command `bfk fix-verify`, which replays the captured runner and writes the newly captured verification log to `.bfk/fix_output.log` without overwriting `.bfk/output.log`; inspect the result.
7. Write `fix.md` with root cause used, fix plan used when present, changed files, verification evidence, risk, and next action.

## Final statuses

- `fixed_verified`: code changed and reproducible capture passed.
- `changed_unverified`: code changed, but no reproducible capture context was available.
- `still_failed`: code changed, but rerun capture still fails.
- `refused`: no confirmed code defect or root cause is `unknown`.
- `blocked`: required files, service, logs, or permissions are unavailable.

## Output language

- Default to Chinese for `.bfk/fix.md` narrative descriptions and user-facing summaries.
- If the user explicitly asks for another language, follow that language for the current task.
- Preserve machine-readable field names/status values, file paths, code symbols, JSON keys, HTTP fields, and quoted logs/errors in their original form.
