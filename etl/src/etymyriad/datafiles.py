"""Where the ETL keeps its files on disk, and how it writes them safely."""

from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path


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
