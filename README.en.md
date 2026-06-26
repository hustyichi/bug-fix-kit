# Bug Fix Kit

Language: [简体中文](README.md) | English

Bug Fix Kit (`bfk`) is a local Codex plugin for repeatable bug reproduction, diagnosis, and fix sessions.

It keeps deterministic mechanics in a small stdlib Python helper CLI and leaves root-cause diagnosis/fix judgment to Codex skills.

## Install

For local development:

```bash
python3 -m pip install -e .
bfk install --yes
```

`bfk install` copies the plugin to `~/plugins/bug-fix-kit`, updates the personal marketplace file at `~/.agents/plugins/marketplace.json`, and prints the next `codex plugin add bug-fix-kit@personal` command. Then enable `Bug Fix Kit` from Codex `/plugins` and start a new Codex thread if skills are not immediately visible.

Advanced local install paths are explicit:

```bash
bfk install --plugin-root . --marketplace ~/.agents/plugins/marketplace.json --yes
```

`--source-root` is accepted as a compatibility alias for `--plugin-root`. Existing installed plugin directories are not overwritten unless `--yes` is passed.

## Local helper CLI

```bash
bfk --help
bfk doctor
bfk init-project --base-url http://localhost:8000 --log-file logs/app.log --header Content-Type=application/json
bfk init-project --base-url http://localhost:8000 --request-sample-file sample.curl
bfk new login_failed account=13900000000
bfk run --timeout 3
```

Implemented CLI commands:

- `bfk install` — copy/register the local plugin and bootstrap/update the personal marketplace.
- `bfk init-project` — create/update `.bfk/PROJECT.md` with base URL, log files, default headers, auth note, and optional request contract from a sample request.
- `bfk new` — create one issue directory and issue-specific `runner.py`.
- `bfk run` — execute the selected issue runner and write one numbered iteration.
- `bfk doctor` — report package/plugin shell status.

The helper CLI intentionally does **not** provide deterministic `bfk diagnose`, `bfk fix`, `bfk status`, `bfk verify`, or `bfk auto` commands. Diagnosis and code fixing require Codex judgment and are exposed as skills.

## Codex workflow

```text
$bfk-init
$bfk-new <issue_name> <key=value ...>
$bfk-run [issue_id]
$bfk-diagnose [issue_id]
$bfk-fix [issue_id]
```

The loop writes evidence under `.bfk/`:

```text
.bfk/
├── PROJECT.md
└── issues/
    └── <issue_id>/
        ├── issue.md
        ├── runner.py
        └── iterations/
            └── 001/
                ├── request.json
                ├── response.json
                ├── output.log
                ├── diagnosis.md   # skill-created, optional until $bfk-diagnose
                └── fix.md         # skill-created, optional until $bfk-fix
```

## Actual mechanics

### Project initialization

`bfk init-project` writes `.bfk/PROJECT.md`. `--header Key=Value` may be repeated; those headers are preserved in generated issue runners. `--auth-note` is documentation only and is not executed by the helper.

When `--request-sample-file sample.curl` or `--request-sample "<curl ...>"` is provided, the helper keeps a redacted raw sample, request contract, parameter mapping table, and concise repository evidence in the same Markdown file. Common curl samples are parsed for method, path, headers, JSON body, and nested JSON-string payloads such as `input[0].content[0].text`.

### Issue creation

`bfk new` requires `.bfk/PROJECT.md`; if it is missing, it exits with a concise error telling the user to run `$bfk-init`.

Parameter handling is intentionally simple:

- `key=value` becomes `PARAMS[key] = value` in `runner.py`.
- free-form positional values are joined into a single `value` parameter when no explicit `value=` is provided.
- when `.bfk/PROJECT.md` has a request sample and `Parameter Contract`, the generated runner copies the full sample request and replaces mapped parameters; omitted mapped parameters keep their sample values.
- bfk does not infer endpoint-specific fields such as passwords or user IDs outside the request contract; edit `PROJECT.md` or the generated `runner.py` when a case needs custom request shape.

Without a request contract, generated runners default to:

- `POST {BASE_URL}/`
- JSON body from `PARAMS`
- headers from `.bfk/PROJECT.md` plus `X-BugFix-Issue`
- `LOG_FILES` from `.bfk/PROJECT.md`
- `AFTER_REQUEST_WAIT_SECONDS = 2`

With a request contract, generated runners default to:

- method/path from the sample request or `Endpoint`
- JSON body from the sample request
- parameters written to `body.*` or nested `text.*` locations from `Parameter Contract`
- nested payloads JSON-encoded back into the user text field
- `${ENV_NAME}` header placeholders expanded from environment variables at runtime

Running `python .bfk/issues/<issue_id>/runner.py` prints the request JSON and does not send HTTP.

### Run artifacts

`bfk run [issue_id]` resolves the selected issue, loads `runner.py`, records file offsets, executes the HTTP request, waits if configured, reads new log content, then writes the next iteration directory.

`response.json` behavior:

- HTTP responses, including 4xx/5xx, are recorded with `transport_error: null`.
- connection failures, bad URLs, malformed request data, and non-serializable payloads are recorded as `transport_error.type = "transport_error"`.
- runner import/config/build failures are recorded as `transport_error.type = "runner_error"`.
- invalid explicit issue IDs fail fast with `bfk: issue not found: <id>` and no traceback.

`output.log` contains only log content appended after the captured offset. If a log file shrinks between offset capture and read, the output includes a `log file truncated` note before reading from the start.

## E2E smoke check

A real mock-service check has been run against the current product:

1. start local `127.0.0.1` mock HTTP server;
2. run `bfk init-project` with `Content-Type` and `Authorization` headers;
3. run `bfk new "login failed" account=13900000000 mode=e2e`;
4. run `bfk run --timeout 3`;
5. verify `request.json`, `response.json`, and `output.log`.

Observed result: mock service received `POST /`, `response.json.status_code` was `200`, `transport_error` was `null`, request headers and JSON body matched the runner, and mock logs were captured in `output.log`.

## MVP boundaries

- `$bfk-run` executes and captures only; it does not diagnose or edit code.
- `$bfk-diagnose` writes `diagnosis.md` only; it does not edit code or run requests.
- `$bfk-fix` writes `fix.md` and may edit code only for clear code defects; it does not run verification.
- No PyPI release automation, demo HTTP app, Web UI, OpenTelemetry, remote logs, YAML config, or auto-fix loop in MVP.
