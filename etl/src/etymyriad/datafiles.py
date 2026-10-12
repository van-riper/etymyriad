"""Where the ETL keeps its files on disk, and how it writes them safely."""

from __future__ import annotations

import contextlib
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterator

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
