"""Environment-driven configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass
from urllib.parse import urlsplit, urlunsplit


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


@dataclass(frozen=True, slots=True)
class Config:
    """Runtime configuration, read from the environment.

    Attributes:
        database_url: Postgres connection string (Neon or local dev).
        dump_path: Filesystem path to the Wiktextract JSONL dump.
        dump_date: The enwiktionary dump date, pinned into every source_ref.
    """

    database_url: str
    dump_path: str
    dump_date: str

    @classmethod
    def from_env(cls) -> Config:
        """Build a Config from the environment.

        Returns:
            A frozen Config with all values populated.

        Raises:
            RuntimeError: If any required environment variable is unset.
        """
        database_url = os.environ.get("DATABASE_URL")
        if not database_url:
            msg = "DATABASE_URL is not set (see .env.example)"
            raise RuntimeError(msg)
        dump_path = os.environ.get("WIKTEXTRACT_DUMP")
        if not dump_path:
            msg = "WIKTEXTRACT_DUMP is not set (see .env.example)"
            raise RuntimeError(msg)
        dump_date = os.environ.get("WIKTEXTRACT_DUMP_DATE")
        if not dump_date:
            msg = "WIKTEXTRACT_DUMP_DATE is not set (see .env.example)"
            raise RuntimeError(msg)

        return cls(
            database_url=database_url,
            dump_path=dump_path,
            dump_date=dump_date,
        )
