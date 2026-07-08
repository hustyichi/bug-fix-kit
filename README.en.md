# Bug Fix Kit

Language: [简体中文](README.md) | English

[![PyPI](https://img.shields.io/pypi/v/bug-fix-kit.svg)](https://pypi.org/project/bug-fix-kit/)

Bug Fix Kit (`bfk`) is a local Codex plugin that turns a local service bug into a clear flow:

```text
capture evidence -> locate the root cause -> discuss a repair plan -> apply the smallest fix
```

It is for cases where you have a local service, a request that reproduces the problem, and a local log file. BFK saves the request, response, and new logs so Codex can reason from evidence instead of guessing.

## Who It Is For

Use BFK when you already have:

- A service you can run locally.
- A request that reproduces the issue, ideally a full curl command.
- A service log file, such as `logs/app.log`.
- A need for Codex to find the root cause and make only the necessary repair.

## Install

Install the plugin from the PyPI package:

```bash
uvx --from bug-fix-kit bfk install --yes
```

If you want to keep the `bfk` command installed, use pip:

```bash
python3 -m pip install bug-fix-kit
bfk doctor
bfk install --yes
```

`bfk install --yes` prints the next command, usually:

```bash
codex plugin add bug-fix-kit@personal
```

Run the printed command, then enable `Bug Fix Kit` from Codex `/plugins`. If the `$bfk-*` skills do not appear immediately, start a new Codex thread.

## Quick Start

Run these commands in **your project**, not in this repository.

### 1. Prepare The Issue Context

Before capture, make sure you have:

- The local service running.
- The base URL, such as `http://127.0.0.1:8000`.
- The log file path, such as `logs/app.log`.
- A request that reproduces the issue.

### 2. Capture Evidence

In Codex, pass the full request context to `$bfk-capture`:

```text
$bfk-capture Use Bug Fix Kit for this login failure.
Local service: http://127.0.0.1:8000
Log file: logs/app.log
Repro request:
curl --location 'http://127.0.0.1:8000/login' \
  --header 'Content-Type: application/json' \
  --data '{"account":"13900000000","password":"bad"}'
```

`$bfk-capture` runs one local request and writes:

- `.bfk/request.json`: the actual request sent.
- `.bfk/response.json`: the response or connection error.
- `.bfk/output.log`: new log lines written during the request window.

To change the request, provide the full context again. With no new params or context, `$bfk-capture` replays the existing `.bfk/runner.py`.

### 3. Locate The Root Cause

```text
$bfk-locate
```

Codex reads the capture artifacts, logs, and related code, then writes `.bfk/root-cause.md`. If the evidence is insufficient, it reports what is missing instead of guessing. When no explicit failure is found, it asks what is wrong before locating.

For a log-only case, use:

```text
$bfk-locate
Log file: logs/error.log
Symptom: login failed
```

`$bfk-locate` first saves those external logs as the current `.bfk/output.log`, then continues through the same root-cause flow.

### 4. Add Probe Logs When Key Evidence Is Missing (Optional)

If `$bfk-locate` reports `unknown` because key logs are missing, let BFK insert temporary probe logs to collect the evidence:

```text
$bfk-probe
```

`$bfk-probe`:

- Inserts a few log lines marked with `BFK-PROBE` at the relevant code paths, driven by the missing evidence in `root-cause.md` (at most 5 probes per round, 2 rounds; never logs passwords, tokens, or other secrets).
- Replays the same request and refreshes `.bfk/output.log` with the probe-enriched logs.
- If the probe logs do not appear (the service likely did not reload), it asks you to restart the service instead of reasoning from missing logs.

Then rerun `$bfk-locate`. After the root cause is located, remove every probe with one command:

```text
$bfk-probe --revert
```

Revert deletes every `BFK-PROBE` line (probes are standalone lines, so deletion restores the original content exactly), then verifies zero residue. While probes remain, new `$bfk-capture` and `$bfk-fix` runs refuse to proceed and remind you to revert first.

### 5. Draft A Repair Plan

```text
$bfk-fix-plan
```

`$bfk-fix-plan` reads `.bfk/root-cause.md` and related code, then writes only the latest `.bfk/fix-plan.md` without editing code. If the plan is not right, give feedback or constraints and run `$bfk-fix-plan` again; it rewrites the current plan.

### 6. Apply The Smallest Fix

```text
$bfk-fix
```

`$bfk-fix` changes code only when `root-cause.md` confirms a code defect. If `.bfk/fix-plan.md` exists, it follows that plan first; without a plan, it derives the smallest fix directly from the root cause. When it can reuse the captured request, it reruns it and writes regression logs to `.bfk/fix_output.log`; otherwise it records the verification gap in `.bfk/fix.md`.

## Output Structure

BFK keeps one active bug scene. A new `$bfk-capture` archives the previous one before replacing the top-level `.bfk/` artifacts.

```text
.bfk/
├── runner.py        # current capture request script
├── request.json     # actual request
├── response.json    # response or error
├── output.log       # new logs during capture (includes probe logs after a probe replay)
├── root-cause.md    # root-cause report
├── probe.json       # probe session state (when $bfk-probe is used)
├── fix-plan.md      # latest repair plan
├── fix.md           # fix record
├── fix_output.log   # new logs during fix verification
└── archive/         # older bug scenes
```

## Logs

BFK reads local file logs. Before running the request, it records the current log file size; after the request, it captures the new content into `.bfk/output.log`.

Notes:

- Use the correct log path, preferably relative to the project root or absolute.
- If logs are written asynchronously, ask BFK to wait longer before capture completes.
- If other requests write to the same file at the same time, `output.log` can include unrelated lines.
- If logs go to Docker stdout, journalctl, or a remote system, first save the relevant lines to a local file, or pass the log content directly to `$bfk-locate`.

Adding a request ID to your application logs makes root-cause location more reliable. If your service supports request id or capture id headers, include one in the capture request.

## FAQ

### Why does `bfk` not have capture / locate / fix commands?

That is expected. The `bfk` CLI only installs and checks the plugin:

```bash
bfk --help
bfk doctor
bfk install --yes
```

Bug work happens through Codex skills:

```text
$bfk-capture
$bfk-locate
$bfk-probe
$bfk-fix-plan
$bfk-fix
```

### Can I use BFK without a curl request?

Yes, but results are weaker. You can provide a base URL, endpoint, headers, and key params so BFK can build a simple request. A real curl command is better because it preserves the exact request shape.

### What if `output.log` is empty?

Check three things:

- The log path passed to `$bfk-capture` is correct.
- The local service really writes to that file.
- The service did not write the log after capture finished.

If needed, use an absolute log path or ask BFK to wait longer after the request.

### Will probe logs stay in my code?

No. Every probe line carries the unique `BFK-PROBE` marker, and `$bfk-probe --revert` removes all of them and verifies zero residue. While probes remain, new `$bfk-capture` and `$bfk-fix` runs refuse to proceed so probes cannot be forgotten or committed by accident.

### Can Codex inspect only an error log?

Yes:

```text
$bfk-locate
Log file: logs/error.log
Symptom: describe the symptom here
```

This can locate a root cause, but usually cannot automatically reproduce the issue or verify the fix.
