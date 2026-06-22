#!/usr/bin/env python3
"""PostToolUse: react to a file an edit tool just wrote.

In order, this script:
1. formats and lints the file in place (ruff for Python, prettier+eslint for
   web), so the edit lands at house style;
2. records the touched area for the Stop test gate (see on_stop.py);
3. lints commit/PR drafts and docs prose for em dashes and the like;
4. sniffs for SQL built by string interpolation;
5. warns when a golden/fixture file is edited.

Must-fix problems (prose-draft violations) exit 2 so Claude corrects them.
Advisories (SQL, golden values) ride back as non-blocking additionalContext.
Formatting just happens; the harness re-reads the changed file.
"""

from __future__ import annotations

import contextlib
import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import common as c

# A query string starts with a statement keyword right after its opening
# quote. Tying the keyword to the quote avoids tripping on prose such as
# "read it from the environment".
PY_SQL = re.compile(
    r"""f['"]{1,3}\s*(?:SELECT|INSERT\s+INTO|UPDATE|DELETE\s+FROM)""",
    re.IGNORECASE,
)
TS_SQL = re.compile(
    r"`\s*(?:SELECT|INSERT\s+INTO|UPDATE|DELETE\s+FROM)",
    re.IGNORECASE,
)
COMMIT_TYPES = r"(feat|fix|refactor|perf|style|docs|build|test|chore|revert)"


def run(cmd: list[str], cwd: Path) -> None:
    """Run a formatter, swallowing any failure so editing never breaks."""
    with contextlib.suppress(OSError, subprocess.SubprocessError):
        subprocess.run(
            cmd, cwd=cwd, capture_output=True, timeout=60, check=False
        )


def format_source(path: Path, root: Path) -> None:
    """Format and auto-fix the file with the right toolchain for its area."""
    parts = path.resolve().parts

    if path.suffix == ".py" and "pipeline" in parts:
        venv_ruff = root / "pipeline" / ".venv" / "bin" / "ruff"
        base = [str(venv_ruff)] if venv_ruff.exists() else ["uv", "run", "ruff"]
        run([*base, "format", str(path)], root / "pipeline")
        run([*base, "check", "--fix", str(path)], root / "pipeline")

    elif "web" in parts and path.suffix in {".ts", ".svelte", ".js", ".json"}:
        web = root / "web"
        bins = web / "node_modules" / ".bin"
        if (bins / "prettier").exists():
            run([str(bins / "prettier"), "--write", str(path)], web)
        if path.suffix in {".ts", ".svelte"} and (bins / "eslint").exists():
            run([str(bins / "eslint"), "--fix", str(path)], web)


def record_touch(path: Path) -> None:
    """Mark the edited area (and mirror files) for later checks."""
    parts = path.resolve().parts
    relp = c.rel(path)
    if path.suffix == ".py" and "pipeline" in parts:
        c.mark_touched("pipeline")
    if "web" in parts and path.suffix in {".ts", ".svelte", ".js"}:
        c.mark_touched("web")
    if relp == "db/schema.sql":
        c.mark_touched("schema")
    if relp == "pipeline/src/etymyriad/model.py":
        c.mark_touched("model")
    if relp == "web/src/lib/types.ts":
        c.mark_touched("types")


def commit_problems(text: str) -> list[str]:
    """Return Conventional Commits violations in a commit message."""
    problems: list[str] = []
    body = text.strip().splitlines()
    subject = body[0] if body else ""
    pattern = rf"^{COMMIT_TYPES}(\(.+\))?!?: .+"
    if subject and not re.match(pattern, subject):
        problems.append(f"Subject is not Conventional Commits: {subject!r}")
    if len(subject) > 50:
        problems.append(
            f"Subject is {len(subject)} chars; the max is 50: {subject!r}"
        )
    if subject.endswith("."):
        problems.append("Subject ends with a period. Drop it.")
    if "Co-Authored-By:" not in text:
        problems.append("Missing Co-Authored-By trailer for AI-assisted work.")
    return problems


def lint_prose(path: Path, must_fix: list[str]) -> None:
    """Lint commit/PR drafts and docs for em dashes, semicolons, and format."""
    relp = c.rel(path)
    name = path.name
    is_commit = name == "COMMIT_EDITMSG"
    is_pr = name == "PR_EDITMSG.md"
    is_docs = (relp.startswith("docs/") and path.suffix == ".md") or (
        relp == "README.md"
    )
    if not (is_commit or is_pr or is_docs):
        return
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return

    # Git keeps comment lines in COMMIT_EDITMSG; drop them before linting.
    if is_commit:
        lines = [ln for ln in text.splitlines() if not ln.startswith("#")]
        text = "\n".join(lines)

    problems: list[str] = []
    scanned = c.strip_code(text) if is_docs else text
    dash_hits = c.find_dash_hits(scanned)
    if dash_hits:
        problems.append(
            "Em/en dashes or '--' stand-ins (rewrite per the no-em-dash "
            "rule):\n" + "\n".join(dash_hits)
        )
    if not is_docs and c.count_semicolons(text) > 1:
        problems.append(
            "More than one semicolon. Prefer periods or commas. "
            "A semicolon is a yellow flag, never a list separator."
        )

    if is_commit:
        problems.extend(commit_problems(text))

    if problems:
        must_fix.append(f"Prose lint on {relp}:\n- " + "\n- ".join(problems))


def sniff_sql(path: Path, text: str, advisories: list[str]) -> None:
    """Flag SQL that looks built by interpolation rather than parameters."""
    if path.suffix == ".py":
        for num, line in enumerate(text.splitlines(), 1):
            if PY_SQL.search(line) and "{" in line:
                advisories.append(
                    f"{c.rel(path)}:{num} an f-string appears to build SQL. "
                    "Use psycopg %s parameters, never interpolation."
                )
    elif path.suffix in {".ts", ".svelte"}:
        # The Neon `sql`...`` tagged template is the safe path and is allowed.
        for num, line in enumerate(text.splitlines(), 1):
            if "${" not in line or not TS_SQL.search(line):
                continue
            if re.search(r"\bsql`", line):
                continue
            advisories.append(
                f"{c.rel(path)}:{num} a template literal interpolates into "
                "SQL outside the sql`` tag. Use the Neon tagged template."
            )


def golden_guard(path: Path, advisories: list[str]) -> None:
    """Warn when a golden/fixture file is edited (it may be a parser bug)."""
    relp = c.rel(path)
    in_tests = "/tests/" in f"/{relp}"
    if in_tests and ("golden" in relp or "fixtures" in relp):
        advisories.append(
            f"Edited a golden/fixture file ({relp}). Per data-integrity, a "
            "golden divergence is a parser bug: fix the parser, do not edit "
            "the golden value to match buggy output."
        )


def main() -> None:
    """Format, lint, and audit the file an edit tool just wrote."""
    event = c.load_event()
    path_s = c.edited_path(event)
    if not path_s:
        sys.exit(0)
    path = Path(path_s)
    root = c.project_dir()

    format_source(path, root)
    record_touch(path)

    must_fix: list[str] = []
    advisories: list[str] = []
    lint_prose(path, must_fix)
    try:
        disk_text = path.read_text(encoding="utf-8")
    except OSError:
        disk_text = ""
    sniff_sql(path, disk_text, advisories)
    golden_guard(path, advisories)

    if must_fix:
        message = "\n\n".join(must_fix)
        if advisories:
            message += "\n\nAlso review:\n- " + "\n- ".join(advisories)
        print(message, file=sys.stderr)
        sys.exit(2)
    if advisories:
        out = {
            "hookSpecificOutput": {
                "hookEventName": "PostToolUse",
                "additionalContext": "Hook review notes:\n- "
                + "\n- ".join(advisories),
            }
        }
        print(json.dumps(out))
    sys.exit(0)


if __name__ == "__main__":
    main()
