"""Tests for the read-only role the web app connects as."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, cast

import psycopg
import psycopg.errors
import psycopg.sql
import pytest
from psycopg.conninfo import make_conninfo

from etymyriad.load import load_edges
from etymyriad.model import Sense, Term

if TYPE_CHECKING:
    from typing import LiteralString

_WEB_ROLE_PATH = Path(__file__).resolve().parents[3] / "db" / "web_role.sql"
_WEB_ROLE_SQL = cast(
    "LiteralString", _WEB_ROLE_PATH.read_text(encoding="utf-8")
)

_WEB_TABLES = (
    "language",
    "variety",
    "dataset",
    "term",
    "sense",
    "edge",
    "pickable_term",
)


@pytest.fixture
def web_role_url(db_url: str) -> str:
    """Grant the web role on a fresh database, as the loading role would.

    Roles are cluster-wide and the cluster outlives each test, so the
    role is created only once.

    Returns:
        A DSN for the same database.
    """
    with psycopg.connect(db_url, autocommit=True) as connection:
        connection.execute(
            "DO $$ BEGIN"
            " CREATE ROLE web_readonly LOGIN;"
            " EXCEPTION WHEN duplicate_object THEN NULL;"
            " END $$"
        )
        connection.execute(_WEB_ROLE_SQL)
    return db_url


def _reload(database_url: str) -> None:
    load_edges(
        database_url,
        [Term("en", "aqua", senses=(Sense("noun", "water"),))],
        dump_date="2026-09-02",
    )


def test_web_role_reads_every_table_after_a_reload(web_role_url: str) -> None:
    """The swap's fresh `public` keeps the web role's read access."""
    _reload(web_role_url)
    with psycopg.connect(web_role_url) as connection:
        connection.execute("SET ROLE web_readonly")
        for table in _WEB_TABLES:
            connection.execute(
                psycopg.sql.SQL("SELECT 1 FROM {} LIMIT 1").format(
                    psycopg.sql.Identifier(table)
                )
            )
        row = connection.execute("SELECT source_ref('en', 'aqua')").fetchone()
    assert row == ("wiktionary:2026-09-02:en:aqua",)


def test_web_role_cannot_write_after_a_reload(web_role_url: str) -> None:
    """The web role gets reads only, on the new generation too."""
    _reload(web_role_url)
    with psycopg.connect(web_role_url) as connection:
        connection.execute("SET ROLE web_readonly")
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            connection.execute("DELETE FROM term")


def test_web_role_sessions_start_with_a_statement_timeout(
    web_role_url: str,
) -> None:
    """A runaway web query gets cancelled instead of holding compute."""
    login_url = make_conninfo(web_role_url, user="web_readonly")
    with psycopg.connect(login_url) as connection:
        row = connection.execute("SHOW statement_timeout").fetchone()
    assert row == ("5s",)
