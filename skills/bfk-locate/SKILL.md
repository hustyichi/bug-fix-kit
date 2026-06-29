---
name: bfk-locate
description: "Locate a code-backed root cause from BFK capture artifacts or explicit logs and write root-cause.md without editing code."
---

# Bug Fix Kit — Locate

Use when the user invokes `$bfk-locate`, or provides logs and symptom context for root-cause analysis.

## Boundary

- Reads the current capture by default: `.bfk/request.json`, `.bfk/response.json`, and `.bfk/output.log` when present.
- Also supports direct log input when the user gives log file(s) plus symptom text and codebase context.
- Reads related local source code to reconstruct the log-code direct chain.
- Writes only `.bfk/root-cause.md`.
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

## Output language

- Default to Chinese for `.bfk/root-cause.md` narrative descriptions and user-facing summaries.
- If the user explicitly asks for another language, follow that language for the current task.
- Preserve machine-readable field names/status values, file paths, code symbols, JSON keys, HTTP fields, and quoted logs/errors in their original form.
