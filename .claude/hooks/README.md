# Claude Code hooks

Project automation that runs around Claude's tool calls. Wired in
`../settings.json`. All scripts are standard-library Python invoked with
`python3`, so they need no virtualenv and start fast. Shared helpers live in
`_common.py`.

| Script | Event · matcher | What it does |
| --- | --- | --- |
| `pre_tool.py` | PreToolUse · `Edit\|MultiEdit\|Write\|Bash` | Blocks writing a real `.env`, hardcoding a Postgres connection string into source, and `git add` of `.env`/`data/`. |
| `post_edit.py` | PostToolUse · `Edit\|MultiEdit\|Write` | Formats and lints the edited file (ruff for Python, prettier+eslint for web), lints commit/PR/doc prose, sniffs interpolated SQL, warns on golden-file edits, and records the touched area. |
| `on_stop.py` | Stop | Runs the test gate for each touched area (`uv run pytest`, `npm run check`) and warns when the `schema -> model -> types` mirror drifts. |

## Feedback channels

- **Block (exit 2):** the secret guard and the prose-draft linter. Claude sees
  the message on stderr and corrects course.
- **Advisory (JSON `additionalContext`):** the SQL sniff and golden-file
  warning. Non-blocking notes Claude can weigh.
- **Silent:** formatting just rewrites the file; the harness re-reads it.

## Touched-area state

`post_edit.py` writes markers to `.claude/.state/touched` (gitignored).
`on_stop.py` reads them to decide which suite to run, then clears them. The
`stop_hook_active` flag prevents a fail-block loop: after one block the turn is
allowed to stop, and the next real edit re-marks the area.

## Verify a hook by hand

Feed it a sample event on stdin:

```sh
echo '{"tool_name":"Write","tool_input":{"file_path":"/x/.env","content":"x"}}' \
  | CLAUDE_PROJECT_DIR="$PWD" python3 .claude/hooks/pre_tool.py; echo "exit $?"
```

Exit `2` means the hook blocked (and printed why on stderr); exit `0` means it
allowed the call.
