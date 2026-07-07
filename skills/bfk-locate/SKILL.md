---
name: bfk-locate
description: "Locate a code-backed root cause from BFK capture artifacts or explicit logs and write root-cause.md without editing code."
---

# Bug Fix Kit — Locate

Use when the user invokes `$bfk-locate`, or provides logs and symptom context for root-cause analysis.

## Boundary

- Reads the current capture by default: `.bfk/request.json`, `.bfk/response.json`, and `.bfk/output.log` when present.
- Loads the captured evidence deterministically through the internal command `bfk locate-load`, which returns the parsed request/response, output log text, and a list of missing evidence files as JSON.
- Also supports direct log input when the user gives log file(s) plus symptom text and codebase context.
- When direct log file(s) are provided, first run one `bfk log-import` command with one `--log-file <path>` flag per file so the raw log content becomes the current `.bfk/output.log`, then run `bfk locate-load`.
- Reads related local source code to reconstruct the log-code direct chain.
- Writes `.bfk/output.log` only for direct log import, then writes `.bfk/root-cause.md`.
- Does not execute requests.
- Does not edit code and does not modify application files.
- Does not write `fix.md`.

## Root-cause standard

- After `bfk locate-load` and before reading source code, check whether the evidence has an explicit failure signal: stack trace, exception, transport error, fatal/error log, or clearly failed response.
- If there is no explicit failure signal, the user must provide an expected result or correctness criteria before root-cause location starts.
- If the expected result or correctness criteria are missing for a no-exception case, stop and ask for them. Do not write `.bfk/root-cause.md` and do not guess from logs alone.
- Default prompt for that blocked case: `当前证据没有发现明确异常。请告知我哪里有问题，方便我准确定位。`
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
