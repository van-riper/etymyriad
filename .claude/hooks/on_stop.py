#!/usr/bin/env python3
"""Stop hook: run after Claude finishes a turn.

For each area edited this session (tracked by post_edit.py) it runs that area's
test gate, and it warns when the three-way schema mirror drifts. Failures exit
2 to ask Claude to keep working. The stop_hook_active flag breaks any loop:
the markers clear each run, and a fresh edit re-marks the area.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import common as c


def run(cmd: list[str], cwd: Path) -> tuple[int, str]:
    """Run a check. A missing binary counts as skipped, not failed."""
    try:
        done = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=300,
            check=False,
        )
        return done.returncode, (done.stdout or "") + (done.stderr or "")
    except FileNotFoundError:
        return 0, ""
    except (OSError, subprocess.SubprocessError) as e:
        return 0, f"(skipped: {e})"


def tail(text: str, lines: int = 25) -> str:
    """Return the last few lines of output for a compact failure report."""
    return "\n".join(text.strip().splitlines()[-lines:])


def mirror_reason(touched: set[str]) -> str | None:
    """Flag a schema edit whose mirror files did not move in the same turn."""
    if "schema" not in touched:
        return None
    missing: list[str] = []
    if "model" not in touched:
        missing.append("pipeline/src/etymyriad/model.py")
    if "types" not in touched:
        missing.append("web/src/lib/types.ts")
    if not missing:
        return None
    return (
        "Three-way mirror: db/schema.sql changed but these were not "
        "updated in step: " + ", ".join(missing) + ". Update them in "
        "the same commit (see the sql-schema-style skill)."
    )


def gate_reasons(touched: set[str], root: Path) -> list[str]:
    """Run each touched area's test gate and collect any failure summaries."""
    reasons: list[str] = []
    if "pipeline" in touched:
        code, out = run(["uv", "run", "pytest", "-q"], root / "pipeline")
        if code != 0:
            reasons.append("pipeline pytest failed:\n" + tail(out))
    if "web" in touched:
        code, out = run(["npm", "run", "check"], root / "web")
        if code != 0:
            reasons.append("web svelte-check failed:\n" + tail(out))
    return reasons


def main() -> None:
    """Run the test gate and mirror guard for areas edited this session."""
    event = c.load_event()
    if event.get("stop_hook_active"):
        sys.exit(0)
    touched = c.read_touched()
    if not touched:
        sys.exit(0)
    root = c.project_dir()

    reasons: list[str] = []
    mirror = mirror_reason(touched)
    if mirror:
        reasons.append(mirror)
    reasons.extend(gate_reasons(touched, root))

    c.clear_touched()

    if reasons:
        print(
            "Turn-end checks need attention:\n\n" + "\n\n".join(reasons),
            file=sys.stderr,
        )
        sys.exit(2)
    sys.exit(0)


if __name__ == "__main__":
    main()
