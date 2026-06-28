---
name: bfk-locate
description: "Locate a code-backed root cause from BFK capture artifacts or explicit logs and write root-cause.md without editing code."
---

# Bug Fix Kit — Locate

Use when the user invokes `$bfk-locate [issue_id]`, or provides logs and issue context for root-cause analysis.

## Boundary

- Reads the latest capture iteration by default: `request.json`, `response.json`, `output.log`, and `capture.md` when present.
- Also supports direct log input when the user gives log file(s) plus issue text and codebase context.
- Reads related local source code to reconstruct the log-code direct chain.
- Writes only `root-cause.md` in the current iteration or issue directory.
- Does not execute requests.
- Does not edit code and does not modify application files.
- Does not write `fix.md`.

## Root-cause standard

- Report `root_cause_found` only when direct-chain evidence links symptom → log/response evidence → code path → root cause.
- Treat a final exception as proximate evidence, not a confirmed root cause, unless the log-code-chain proves why it happened.
- Report `unknown` when evidence is insufficient; list the missing evidence.
- Report `blocked` when service, logs, inputs, or code context are unavailable enough to prevent analysis.
- Do not guess. Do not present a plausible cause as confirmed without direct-chain evidence.

## `root-cause.md` fields

- `status`: `root_cause_found`, `unknown`, or `blocked`.
- `symptom`
- `direct_chain`
- `root_cause`
- `evidence`
- `related_code`
- `missing_evidence`
- `recommended_fix`
- `confidence`
