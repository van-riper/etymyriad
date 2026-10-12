"""Where the ETL keeps its files on disk, and how it writes them safely."""

from __future__ import annotations

import contextlib
import json
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator

DATA_DIR = Path(__file__).resolve().parents[3] / "data"


def data_path() -> Path:
    """Locate the filtered dump.

    Returns:
        Its path in `DATA_DIR`, whether or not it exists.
    """
    return DATA_DIR / "etymyriad-data.jsonl"


def edges_path() -> Path:
    """Locate the edge file.

    Returns:
        Its path in `DATA_DIR`, whether or not it exists.
    """
    return DATA_DIR / "etymyriad-edges.jsonl"


def is_current(edges: Path, dump: Path) -> bool:
    """Tell whether an edge file was written after its dump.

    Returns:
        True when the edge file exists and is no older than the dump.
    """
    try:
        return edges.stat().st_mtime >= dump.stat().st_mtime
    except FileNotFoundError:
        return False


@contextlib.contextmanager
def staged_path(path: Path) -> Iterator[Path]:
    """Yield a sibling temp path that replaces `path` once the block ends.

    Readers pick files by name, so a crashed or interrupted write must
    never leave a partial file under a real one. A block that raises
    deletes the temp file instead.

    Args:
        path: The file the block's output should end up at.

    Yields:
        The temp path to write to.
    """
    staged = path.with_name(f"{path.name}.tmp")
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        yield staged
        staged.replace(path)
    finally:
        staged.unlink(missing_ok=True)


def fields_path(data_file: Path) -> Path:
    """Locate the sidecar listing the fields a filtered dump kept.

    Returns:
        The `.fields.json` path beside the dump.
    """
    stem = data_file.name.removesuffix(".jsonl")
    return data_file.with_name(f"{stem}.fields.json")


def write_fields(data_file: Path, paths: Iterable[str]) -> None:
    """Record the field paths a filtered dump kept, beside it.

    Args:
        data_file: The filtered dump the paths describe.
        paths: Dotted field paths, as `normalize.field_paths` gives them.
    """
    with staged_path(fields_path(data_file)) as staged:
        text = json.dumps(sorted(paths), indent=2)
        staged.write_text(f"{text}\n", encoding="utf-8")


def read_fields(data_file: Path) -> frozenset[str] | None:
    """Read the field paths a filtered dump kept.

    Returns:
        The paths, or None when the dump has no sidecar.
    """
    try:
        text = fields_path(data_file).read_text(encoding="utf-8")
    except FileNotFoundError:
        return None
    return frozenset(json.loads(text))
