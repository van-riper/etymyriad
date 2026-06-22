"""Shared helpers for the etymyriad Claude Code hooks.

Every hook reads a JSON event on stdin (see the Claude Code hooks docs) and
then fixes files, emits advisory context, or blocks a tool call. Everything
here is standard-library only, so the scripts start fast and need no venv.
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Any

type HookEvent = dict[str, Any]

# Em dash and en dash. The house rule bans both, plus a "--" stand-in.
EM_DASH = "\u2014"
EN_DASH = "\u2013"


def load_event() -> HookEvent:
    """Parse the hook event JSON from stdin.

    Returns:
        The decoded event, or an empty dict on any read/parse error.
    """
    try:
        return json.loads(sys.stdin.read() or "{}")
    except (ValueError, OSError):
        return {}


def project_dir() -> Path:
    """Return the repo root from $CLAUDE_PROJECT_DIR with a cwd fallback."""
    env = os.environ.get("CLAUDE_PROJECT_DIR")
    return Path(env) if env else Path.cwd()


def get_tool_input(event: HookEvent) -> dict[str, Any]:
    """Return the event's tool_input object, or an empty dict."""
    data = event.get("tool_input")
    return data if isinstance(data, dict) else {}


def edited_path(event: HookEvent) -> str | None:
    """Return the absolute path an edit tool wrote, if the event carries one."""
    return get_tool_input(event).get("file_path")


def written_text(event: HookEvent) -> str:
    """Return the text an edit introduced.

    Covers Write content, Edit new_string, and MultiEdit edits.
    """
    tool_input = get_tool_input(event)
    parts: list[str] = []
    if isinstance(tool_input.get("content"), str):
        parts.append(tool_input["content"])
    if isinstance(tool_input.get("new_string"), str):
        parts.append(tool_input["new_string"])
    edits = tool_input.get("edits")
    if isinstance(edits, list):
        for edit in edits:
            piece = edit.get("new_string") if isinstance(edit, dict) else None
            if isinstance(piece, str):
                parts.append(piece)
    return "\n".join(parts)


def rel(path: str | Path) -> str:
    """Return path relative to the repo root, or the input on failure."""
    try:
        root = project_dir().resolve()
        return str(Path(path).resolve().relative_to(root))
    except (ValueError, OSError):
        return str(path)


# --- Touched-area state (shared between post_edit and on_stop) ---------------


def _state_dir() -> Path:
    out = project_dir() / ".claude" / ".state"
    out.mkdir(parents=True, exist_ok=True)
    return out


def mark_touched(area: str) -> None:
    """Record that an area changed this session (e.g. pipeline, web)."""
    target = _state_dir() / "touched"
    seen = (
        set(target.read_text(encoding="utf-8").split())
        if target.exists()
        else set()
    )
    seen.add(area)
    target.write_text("\n".join(sorted(seen)) + "\n", encoding="utf-8")


def read_touched() -> set[str]:
    """Return the set of areas marked since the last clear."""
    target = _state_dir() / "touched"
    return (
        set(target.read_text(encoding="utf-8").split())
        if target.exists()
        else set()
    )


def clear_touched() -> None:
    """Forget all touched-area markers."""
    target = _state_dir() / "touched"
    if target.exists():
        target.unlink()


# --- Prose checks (shared by the draft/doc linter) ---------------------------


def strip_code(text: str) -> str:
    """Drop fenced blocks and inline-code spans so prose checks skip code."""
    text = re.sub(r"```.*?```", "", text, flags=re.DOTALL)
    return re.sub(r"`[^`]*`", "", text)


def find_dash_hits(text: str) -> list[str]:
    """Return labelled lines holding an em dash, en dash, or "--" stand-in."""
    hits: list[str] = []
    for num, line in enumerate(text.splitlines(), 1):
        bad_dash = EM_DASH in line or EN_DASH in line
        if bad_dash or re.search(r"\S\s?--\s?\S", line):
            hits.append(f"  line {num}: {line.strip()[:72]}")
    return hits


def count_semicolons(text: str) -> int:
    """Count semicolons outside code spans."""
    return strip_code(text).count(";")
