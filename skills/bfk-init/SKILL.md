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

1. Gather or infer local service URL, log files, request defaults, auth note, and fix principles.
2. Prefer the helper command:

   ```bash
   bfk init-project --base-url <url> --log-file <path> [--header Key=Value] [--auth-note <note>]
   ```

3. If the helper is unavailable, write `.bfk/PROJECT.md` manually using the PRD shape.
4. Report the path and recommend `$bfk-new` next.
