"""Atomically promote `loading` to `public`, blue/green style."""

from __future__ import annotations

import logging
import time

import psycopg
import psycopg.errors

from etymyriad.load._schema import (
    _LIVE_SCHEMA,
    _TARGET_SCHEMA,
)

_log = logging.getLogger(__name__)

_SWAP_SCHEMAS_SQL = f"""
    SET LOCAL lock_timeout = '5s';
    DROP SCHEMA {_LIVE_SCHEMA} CASCADE;
    ALTER SCHEMA {_TARGET_SCHEMA} RENAME TO {_LIVE_SCHEMA};
"""

# One wait before each retry, so the swap gets three attempts in all.
_RETRY_DELAYS_SECONDS = (5.0, 15.0)


def _swap_schemas(connection: psycopg.Connection) -> None:
    """Atomically replace `public` with `loading`, retrying lock timeouts.

    The old generation is dropped, not kept. Rollback is Neon's instant
    restore (6h of history) or a re-run of the previous dump. A
    `lock_timeout` caps each attempt's wait on a long-running reader's
    conflicting lock. A timed-out attempt is retried after a short
    sleep, since failing here would discard a finished generation. The
    last attempt's timeout, or any other error, propagates.
    """
    for delay_seconds in _RETRY_DELAYS_SECONDS:
        try:
            _swap_schemas_once(connection)
        except psycopg.errors.LockNotAvailable:
            _log.warning(
                "schema swap hit its lock timeout; retrying in %.0fs",
                delay_seconds,
            )
            time.sleep(delay_seconds)
        else:
            return
    _swap_schemas_once(connection)


def _swap_schemas_once(connection: psycopg.Connection) -> None:
    """Run the swap in one transaction.

    DDL is transactional in Postgres, so a failure here leaves the
    pre-swap state untouched.
    """
    with connection.transaction():
        connection.execute(_SWAP_SCHEMAS_SQL)
