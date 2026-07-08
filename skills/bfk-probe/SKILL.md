---
name: bfk-probe
description: "Insert reversible BFK-PROBE log lines to collect missing key evidence, replay the capture, and revert every probe on demand."
---

# Bug Fix Kit — Probe

Use when the user invokes `$bfk-probe` after `$bfk-locate` reported `unknown` with missing key logs, or invokes `$bfk-probe --revert` to remove every probe line.

## Boundary

- Requires a reproducible capture (`.bfk/runner.py`); without one, report blocked and ask for `$bfk-capture` first.
- Is the only BFK step allowed to insert temporary probe log lines into application code; every inserted line must be a standalone logging statement containing the literal marker `BFK-PROBE`.
- Inserts at most 5 probe lines per round and runs at most 2 probe rounds per capture; `bfk probe-run` enforces the round limit.
- Never inserts probes inside tight loops or hot paths.
- Never logs secrets: no passwords, tokens, cookies, authorization header values, or full request bodies; log only ids, branch decisions, and the specific values named in `missing_evidence`.
- Always includes one sentinel probe on the request entry path so probe effectiveness is verifiable.
- `bfk probe-run` writes `.bfk/probe.json` and refreshes the regular `.bfk/output.log` by replaying the same request, so later steps read one unified evidence log.
- Does not change any application logic; probe lines are pure logging additions on their own lines.
- Does not analyze root cause and does not write `root-cause.md`, `fix-plan.md`, or `fix.md`.
- Revert runs only through `bfk probe-revert`, which deletes every line containing the marker (probe lines are standalone, so deletion restores the pre-probe content exactly) and must verify zero `BFK-PROBE` residue.

## Probe workflow

1. Read `.bfk/root-cause.md` (`missing_evidence` in particular, when present) and the related code to choose the smallest set of probe points.
2. Tell the user which file and location each probe goes to, what it prints, and which missing evidence it serves.
3. Insert the probe lines, each on its own line, each containing `BFK-PROBE`.
4. Run one `bfk probe-run` command with one `--file <path>` flag per instrumented file; it replays the current runner and refreshes `.bfk/output.log` with the probe-enriched evidence.
5. If the summary reports `sentinel_seen: false`, the service likely did not reload the probes: report blocked with the default prompt `探针日志未生效，服务可能未重载。请重启本地服务后再次运行 $bfk-probe。` and do not draw any conclusion from missing probe logs.
6. If `sentinel_seen: true`, summarize the newly collected probe evidence, then ask the user to rerun `$bfk-locate`, and remind them that `$bfk-probe --revert` removes all probes after root-cause location.

## Revert workflow

1. On `$bfk-probe --revert`, run `bfk probe-revert`.
2. If `residue_files` is not empty, open each listed file, delete the remaining `BFK-PROBE` lines manually, and run `bfk probe-revert` again until it reports `clean: true`.
3. Summarize the reverted files and the method used for each (`strip`, `clean`, or `missing`).

## Output language

- Default to Chinese for user-facing summaries and probe explanations.
- If the user explicitly asks for another language, follow that language for the current task.
- Preserve machine-readable field names/status values, file paths, code symbols, JSON keys, HTTP fields, and quoted logs/errors in their original form.
