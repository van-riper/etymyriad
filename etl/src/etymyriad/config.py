"""The ETL's database, filtered dump, scope, and tuning values."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import TYPE_CHECKING
from urllib.parse import urlsplit, urlunsplit

from etymyriad import datafiles

if TYPE_CHECKING:
    from etymyriad.languages._model import SetCode

# Matches web/src/lib/server/db.ts's dev fallback: the standard local
# role/database this project's setup docs have devs create. Makes
# DATABASE_URL optional for ordinary local dev; never used for a real
# DATABASE_URL (Neon).
LOCAL_DATABASE_URL = "postgres://etymyriad:etymyriad@localhost:5432/etymyriad"

# Wiktionary language-family codes whose languages the filter keeps.
SCOPE_FAMILIES: frozenset[SetCode] = frozenset({
    "ine",  # Indo-European
    # "sit",  # Sino-Tibetan
    # "urj",  # Uralic
    # "afa",  # Afro-Asiatic
    # "map",  # Austronesian
    # "jpx",  # Japonic
    # "trk",  # Turkic
    # "qfa-not",  # Uncategorized
})

# Remote services the ETL reads from. Wikimedia asks every client to send
# a User-Agent that names the project and how to reach it.
USER_AGENT = "etymyriad-etl (https://etymyriad.com)"
WIKTIONARY_API_URL = "https://en.wiktionary.org/w/api.php"
WIKIDATA_SPARQL_URL = "https://query.wikidata.org/sparql"
KAIKKI_RAWDATA_URL = "https://kaikki.org/dictionary/rawdata.html"
KAIKKI_RAW_DUMP_URL = (
    "https://kaikki.org/dictionary/raw-wiktextract-data.jsonl.gz"
)

# How hard the ETL leans on those services. The delay and limit apply
# to crosscheck, which fetches one rendered page per tree.
HTTP_TIMEOUT_SECONDS = 120
DUMP_DOWNLOAD_ATTEMPTS = 3
DUMP_PROGRESS_INTERVAL_SECONDS = 5
CROSSCHECK_FETCH_DELAY_SECONDS = 1
DEFAULT_CROSSCHECK_LIMIT = 25

# Sanity gates that stop a bad load before it replaces the live data.
# Drift is the largest allowed change in term or edge count against the
# generation, so the share is the most edges that may name an unknown
# language code.
MAX_COUNT_DRIFT = 0.10
MAX_UNKNOWN_LANGUAGE_SHARE = 0.001

# The schema swap waits on locks held by long-running readers. Each
# attempt gives up after the lock timeout. One wait comes before each
# retry, so the swap gets three attempts in all.
SWAP_LOCK_TIMEOUT_SECONDS = 5
SWAP_RETRY_DELAYS_SECONDS = (5.0, 15.0)

# Memory Postgres may use while building the indexes the bulk merge deferred.
INDEX_BUILD_MAINTENANCE_WORK_MEM = "1GB"

# Log volume: how often progress lines appear while streaming, and
# how many unmapped relation names the normalize summary lists.
PROGRESS_LOG_INTERVAL = 100_000
UNMAPPED_LOG_LIMIT = 30


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


def _filtered_dump() -> str | None:
    """Find the filtered dump in the data directory.

    Returns:
        Its path, or None when the file is absent.
    """
    path = datafiles.data_path()
    return str(path) if path.is_file() else None


@dataclass(frozen=True, slots=True)
class Config:
    """Runtime configuration: the database URL and the filtered dump.

    Attributes:
        database_url: Postgres connection string (Neon or local dev).
        dump_path: The filtered dump `filter` writes, or None when the
            file is absent.
    """

    database_url: str = field(repr=False)
    dump_path: str | None

    @classmethod
    def from_env(cls) -> Config:
        """Build a Config from the environment, defaulting where possible.

        Returns:
            A frozen Config, falling back to the standard local dev DB
            when DATABASE_URL is unset.
        """
        return cls(
            database_url=os.environ.get("DATABASE_URL", LOCAL_DATABASE_URL),
            dump_path=_filtered_dump(),
        )
