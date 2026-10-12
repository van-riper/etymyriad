"""Shared test fixtures.

DB-backed tests spawn their own throwaway Postgres via pytest-postgresql,
which shells out to initdb/pg_ctl on PATH. Each test gets a fresh,
schema-loaded database created and dropped by the DatabaseJanitor, so the
suite needs no external server.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from psycopg.conninfo import make_conninfo
from pytest_postgresql import factories

if TYPE_CHECKING:
    import psycopg

_SCHEMA = Path(__file__).resolve().parents[2] / "db" / "schema.sql"

postgresql_proc = factories.postgresql_proc(
    executable="/usr/bin/pg_ctl", load=[_SCHEMA]
)
postgresql = factories.postgresql("postgresql_proc")


@pytest.fixture
def db_url(postgresql: psycopg.Connection) -> str:
    """Return a DSN for the fresh, schema-loaded test database.

    Returns:
        A psycopg-compatible connection string.
    """
    return make_conninfo(**postgresql.info.get_parameters())


@pytest.fixture(autouse=True)
def data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point the ETL's data directory at a throwaway path, not yet created.

    Autouse, so no test can read from or prune the real data/.

    Returns:
        The redirected data directory.
    """
    path = tmp_path / "data"
    monkeypatch.setattr("etymyriad.datafiles.DATA_DIR", path)
    return path
