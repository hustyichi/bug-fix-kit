---
name: bfk-fix-plan
description: "Draft or update the latest repair plan from a confirmed BFK root-cause.md without editing code."
---

# Bug Fix Kit — Fix Plan

Use when the user invokes `$bfk-fix-plan` after `$bfk-locate` has written `.bfk/root-cause.md`, or when the user gives feedback on an existing `.bfk/fix-plan.md`.

## Boundary

- Reads `.bfk/root-cause.md`, existing `.bfk/fix-plan.md` when present, user feedback in the current conversation, and related code files.
- Does not modify application code.
- Does not write `.bfk/fix.md`.
- Does not run `bfk fix-verify` or claim verification.
- Writes only the latest repair plan to `.bfk/fix-plan.md`.
- Does not maintain approval state, status fields, revision history, or append-only feedback history.
- `$bfk-fix` remains a separate step; the user decides when to run it.

## Workflow

1. Read `.bfk/root-cause.md`.
2. If `root-cause.md` is missing, `unknown`, `blocked`, or lacks a confirmed code defect, write `.bfk/fix-plan.md` explaining why a concrete repair plan is not available yet and what evidence is needed.
3. Read related code enough to make the plan specific to files, functions, contracts, and tests.
4. If `.bfk/fix-plan.md` already exists, treat it as the previous candidate plan. Apply the user's latest feedback and rewrite the whole file as the new current plan.
5. Preserve still-relevant user constraints in the current plan. Remove constraints only when the user supersedes them.
6. Prefer the smallest root-cause fix. Reject unrelated refactors, broad rewrites, public API changes, and guessed fixes unless the confirmed defect requires them.
7. Write `.bfk/fix-plan.md` with the current plan only.

## `fix-plan.md` fields

- `root_cause_used`
- `user_feedback_applied`
- `current_constraints`
- `proposed_fix`
- `files_to_change`
- `rejected_options`
- `verification_plan`
- `open_questions`

## Output language

- Default to Chinese for `.bfk/fix-plan.md` narrative descriptions and user-facing summaries.
- If the user explicitly asks for another language, follow that language for the current task.
- Preserve machine-readable field names/status values, file paths, code symbols, JSON keys, HTTP fields, and quoted logs/errors in their original form.
