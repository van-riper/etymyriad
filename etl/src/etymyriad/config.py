"""Environment-driven configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import date
from urllib.parse import urlsplit, urlunsplit

from etymyriad import datafiles

# Matches web/src/lib/server/db.ts's dev fallback: the standard local
# role/database this project's setup docs have devs create. Makes
# DATABASE_URL optional for ordinary local dev; never used for a real
# DATABASE_URL (Neon).
LOCAL_DATABASE_URL = "postgres://etymyriad:etymyriad@localhost:5432/etymyriad"


def redact_dsn(dsn: str) -> str:
    """Mask the password in a connection string for safe logging.

    Args:
        dsn: A database connection URL, possibly carrying a password.

    Returns:
        The DSN with any password replaced by "***", else unchanged.
    """
    parts = urlsplit(dsn)
    if parts.password is None:
        return dsn
    userinfo = parts.username or ""
    host = parts.hostname or ""
    if parts.port is not None:
        host = f"{host}:{parts.port}"
    netloc = f"{userinfo}:***@{host}"
    return urlunsplit(parts._replace(netloc=netloc))


def redact_secrets(dsn: str, text: str) -> str:
    """Scrub a DSN's password out of arbitrary text.

    Driver errors sometimes echo the raw DSN in their message; this
    catches that leak before the text reaches a log.

    Args:
        dsn: The connection string whose password must never leak.
        text: Free text that may embed the raw dsn.

    Returns:
        text with any occurrence of the password masked.
    """
    password = urlsplit(dsn).password
    if not password:
        return text
    return text.replace(password, "***")


def _dump_date_from_env() -> str | None:
    """Read WIKTEXTRACT_DUMP_DATE, which every citation will name.

    Returns:
        The date string, or None when the variable is unset.

    Raises:
        ValueError: If the value isn't a real YYYY-MM-DD date.
    """
    value = os.environ.get("WIKTEXTRACT_DUMP_DATE")
    if value is None:
        return None
    try:
        is_iso_date = date.fromisoformat(value).isoformat() == value
    except ValueError:
        is_iso_date = False
    if not is_iso_date:
        msg = "WIKTEXTRACT_DUMP_DATE must be YYYY-MM-DD"
        raise ValueError(msg)
    return value


def _filtered_dump() -> str | None:
    """Find the filtered dump in the data directory.

    Returns:
        Its path, or None when `filter` has never run.
    """
    path = datafiles.data_path()
    return str(path) if path.is_file() else None


@dataclass(frozen=True, slots=True)
class Config:
    """Runtime configuration, read from the environment.

    Attributes:
        database_url: Postgres connection string (Neon or local dev).
        dump_path: Filesystem path to the Wiktextract JSONL dump, or None
            when unset and no filtered dump exists.
        dump_date: The enwiktionary dump date that citations name, or
            None when unset. Only `load` needs it.
    """

    database_url: str = field(repr=False)
    dump_path: str | None
    dump_date: str | None

    @classmethod
    def from_env(cls) -> Config:
        """Build a Config from the environment, defaulting where possible.

        Returns:
            A frozen Config, falling back to the standard local dev DB
            and the newest filtered dump for anything the environment
            doesn't override.
        """
        return cls(
            database_url=os.environ.get("DATABASE_URL", LOCAL_DATABASE_URL),
            dump_path=os.environ.get("WIKTEXTRACT_DUMP") or _filtered_dump(),
            dump_date=_dump_date_from_env(),
        )
