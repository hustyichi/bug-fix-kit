---
name: bfk-init
description: Initialize Bug Fix Kit project knowledge in .bfk/PROJECT.md for a local service.
---

# Bug Fix Kit — Init

Use when the user invokes `$bfk-init` or wants to initialize project-level bfk debugging knowledge.

## Boundary

- Creates or updates only `.bfk/PROJECT.md`.
- Does not create issue directories.
- Does not create issue runners.
- Does not run requests.
- Does not diagnose.
- Does not fix code.

## Workflow

1. Gather or infer local service URL, log files, default request headers, auth note, request sample, and fix principles.
2. When the user provides a real curl/request sample, preserve it through the helper so `.bfk/PROJECT.md` contains the redacted raw sample, request contract, parameter contract, and repository evidence.
3. Cross-check the sample against the current repository when possible: endpoint route, request model, JSON parsing point, action name, and key params. Keep evidence concise; do not paste large search output.
4. Write `.bfk/PROJECT.md` directly. Do not invoke `bfk init-project`; the CLI is for plugin management, not the core Codex workflow.
5. Preserve request headers that generated runners should send. Prefer env placeholders for secrets, for example `Bearer ${LITELLM_API_KEY}`. `auth-note` style content is documentation only.
6. Use the current PRD shape: Local Service, Logs, Log Capture, Request Defaults, optional Auth, optional Request Sample / Request Contract / Parameter Contract / Repository Evidence, Fix Principles.
7. Report the path and recommend `$bfk-new` next.
