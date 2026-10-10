"""Atomically promote `loading` to `public`, blue/green style."""

from __future__ import annotations

from typing import TYPE_CHECKING

from etymyriad.load._schema import (
    _LIVE_SCHEMA,
    _TARGET_SCHEMA,
)

if TYPE_CHECKING:
    import psycopg

_SWAP_SCHEMAS_SQL = f"""
    SET LOCAL lock_timeout = '5s';
    DROP SCHEMA {_LIVE_SCHEMA} CASCADE;
    ALTER SCHEMA {_TARGET_SCHEMA} RENAME TO {_LIVE_SCHEMA};
"""


def _swap_schemas(connection: psycopg.Connection) -> None:
    """Atomically replace `public` with `loading`.

    The old generation is dropped, not kept. Rollback is Neon's instant
    restore (6h of history) or a re-run of the previous dump. Both
    statements run in one transaction: DDL is transactional in
    Postgres, so a failure here leaves the pre-swap state untouched. A
    `lock_timeout` caps the wait on a long-running reader's conflicting
    lock, so a contended swap fails fast and retriably rather than
    hanging.
    """
    with connection.transaction():
        connection.execute(_SWAP_SCHEMAS_SQL)
