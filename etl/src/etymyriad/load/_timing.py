"""Log how long a slow load step took."""

import logging
import time
from contextlib import contextmanager
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Generator

_log = logging.getLogger(__name__)


@contextmanager
def logged_step(name: str) -> Generator[None]:
    """Log `name` with its duration when the wrapped block ends."""
    started = time.monotonic()
    try:
        yield
    finally:
        _log.info("%s took %.1fs", name, time.monotonic() - started)
