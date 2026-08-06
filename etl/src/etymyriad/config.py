"""Environment-driven configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

# Matches web/src/lib/server/db.ts's dev fallback: the standard local
# role/database this project's setup docs have devs create. Makes
# DATABASE_URL optional for ordinary local dev; never used for a real
# DATABASE_URL (Neon).
LOCAL_DATABASE_URL = "postgres://etymyriad:etymyriad@localhost:5432/etymyriad"

# The standard acquired-dump location (see CLAUDE.md), resolved from
# this file's own path rather than the process's cwd, since ETL
# commands are conventionally run from etl/ (uv run etymyriad ...).
DEFAULT_DUMP_PATH = str(
    Path(__file__).resolve().parents[3] / "data" / "raw" / "indo-european.jsonl"
)

# The enwiktionary dump date currently pinned into every source_ref.
# Bump this by hand (like a version) whenever data/raw/indo-european.jsonl
# is refreshed from a newer kaikki.org dump -- never leave it stale,
# since it's asserted as citation provenance on every lexeme/edge.
DEFAULT_DUMP_DATE = "2026-06-01"


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


@dataclass(frozen=True, slots=True)
class Config:
    """Runtime configuration, read from the environment.

    Attributes:
        database_url: Postgres connection string (Neon or local dev).
        dump_path: Filesystem path to the Wiktextract JSONL dump.
        dump_date: The enwiktionary dump date, pinned into every source_ref.
    """

    database_url: str = field(repr=False)
    dump_path: str
    dump_date: str

    @classmethod
    def from_env(cls) -> Config:
        """Build a Config from the environment, defaulting every value.

        Returns:
            A frozen Config, falling back to the standard local dev
            DB/dump for anything the environment doesn't override.
        """
        return cls(
            database_url=os.environ.get("DATABASE_URL", LOCAL_DATABASE_URL),
            dump_path=os.environ.get("WIKTEXTRACT_DUMP", DEFAULT_DUMP_PATH),
            dump_date=os.environ.get(
                "WIKTEXTRACT_DUMP_DATE", DEFAULT_DUMP_DATE
            ),
        )
