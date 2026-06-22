#!/usr/bin/env python3
"""PreToolUse guard: stop a secret leak before the tool runs.

Blocks three things and feeds the reason back to Claude with exit code 2:
- writing a real .env (only .env.example is allowed),
- hardcoding a Postgres connection string into source,
- shell commands that would stage .env or data/.

See .claude/rules/security.md.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path, PurePath

sys.path.insert(0, str(Path(__file__).resolve().parent))

import common as c

# A connection string carrying inline credentials: user:pass@host.
CONN = re.compile(r"postgres(?:ql)?://[^\s:/@]+:[^\s/@]+@")


def block(message: str) -> None:
    """Print the reason to stderr and exit 2 so Claude sees and adapts."""
    print(f"[security hook] {message}", file=sys.stderr)
    sys.exit(2)


def main() -> None:
    """Inspect the pending tool call and block on a secret-leak risk."""
    event = c.load_event()
    tool = event.get("tool_name", "")
    tool_input = c.get_tool_input(event)

    if tool in {"Write", "Edit", "MultiEdit"}:
        path = c.edited_path(event) or ""
        name = PurePath(path).name
        if name == ".env" or (
            name.startswith(".env") and name != ".env.example"
        ):
            block(
                f"Refusing to write {c.rel(path)}. Real dotenv files are "
                "gitignored and credentials come only from the environment. "
                "Put placeholders in .env.example instead."
            )
        parts = Path(path).parts
        src_like = path.endswith((".py", ".ts", ".svelte", ".js")) and (
            "pipeline" in parts or "web" in parts
        )
        if src_like and CONN.search(c.written_text(event)):
            block(
                "A hardcoded Postgres connection string was detected in "
                f"{c.rel(path)}. Read DATABASE_URL from the environment; never "
                "embed credentials in source, tests, or fixtures."
            )

    if tool == "Bash":
        cmd = tool_input.get("command", "")
        adds = re.search(r"\bgit\s+add\b", cmd)
        if adds and (
            re.search(r"\.env(?![\w.])", cmd) or re.search(r"(^|\s)data/", cmd)
        ):
            block(
                "This command would stage .env or data/. Both are gitignored "
                "and must never be committed. Stage only intended files."
            )
        if re.search(r"git\s+add\b.*(-f\b|--force)", cmd):
            block(
                "Refusing 'git add --force': it bypasses .gitignore, which is "
                "what keeps .env and data/ out of the repo."
            )

    sys.exit(0)


if __name__ == "__main__":
    main()
