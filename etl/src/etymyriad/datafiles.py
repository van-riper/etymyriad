"""Where the ETL keeps its files on disk, and how it writes them safely."""

from __future__ import annotations

import contextlib
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator

DATA_DIR = Path(__file__).resolve().parents[3] / "data"
DATA_PREFIX = "etymyriad-data"
EDGES_PREFIX = "etymyriad-edges"

type Stamp = str

_STAMP_FORMAT = "%Y%m%dT%H%M%SZ"
_STAMPED_NAME = re.compile(
    rf"(?P<prefix>{DATA_PREFIX}|{EDGES_PREFIX})-(?P<stamp>\d{{8}}T\d{{6}}Z)"
    r"(?P<suffix>\.jsonl|\.fields\.json)"
)


def new_stamp() -> Stamp:
    """Stamp the current moment, in UTC, for a new file's name.

    Returns:
        The stamp, in ISO 8601 basic format, which sorts in time order.
    """
    return datetime.now(UTC).strftime(_STAMP_FORMAT)


def stamp_of(path: str | Path) -> Stamp | None:
    """Read the stamp off a filtered dump's file name.

    Returns:
        The stamp, or None for any name but `etymyriad-data-<stamp>.jsonl`.
    """
    match = _STAMPED_NAME.fullmatch(Path(path).name)
    if match is None or match["prefix"] != DATA_PREFIX:
        return None
    if match["suffix"] != ".jsonl":
        return None
    return match["stamp"]


def data_path(stamp: Stamp) -> Path:
    """Locate the filtered dump with this stamp.

    Returns:
        Its path in `DATA_DIR`, whether or not it exists.
    """
    return DATA_DIR / f"{DATA_PREFIX}-{stamp}.jsonl"


def edges_path(stamp: Stamp) -> Path:
    """Locate the edge file with this stamp.

    Returns:
        Its path in `DATA_DIR`, whether or not it exists.
    """
    return DATA_DIR / f"{EDGES_PREFIX}-{stamp}.jsonl"


def latest_file(data_dir: Path, prefix: str) -> Path | None:
    """Find the newest stamped `<prefix>-<stamp>.jsonl` in a directory.

    Args:
        data_dir: The directory to search; it need not exist.
        prefix: `DATA_PREFIX` or `EDGES_PREFIX`.

    Returns:
        The file with the latest stamp, or None if there is none.
    """
    candidates = sorted(
        path
        for path in data_dir.glob(f"{prefix}-*.jsonl")
        if _STAMPED_NAME.fullmatch(path.name)
    )
    return candidates[-1] if candidates else None


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


def stale_files(data_dir: Path, keep: Stamp | None) -> list[Path]:
    """List the stamped files older than the newest filtered dump.

    A stamp group is a filtered dump, its sidecar, and its edge file;
    every file of an older group is listed together, so none is left
    orphaned. Only stamped names match, so the raw dump and temp files
    are never listed.

    Args:
        data_dir: The directory to search; it need not exist.
        keep: A stamp to spare even when older, or None.

    Returns:
        The stale files in name order, or [] when no filtered dump
        exists to measure against.
    """
    latest = latest_file(data_dir, DATA_PREFIX)
    newest = None if latest is None else stamp_of(latest)
    if newest is None:
        return []
    stale: list[Path] = []
    for path in sorted(data_dir.iterdir()):
        match = _STAMPED_NAME.fullmatch(path.name)
        if match and match["stamp"] < newest and match["stamp"] != keep:
            stale.append(path)
    return stale
