"""Tests for configuration and DSN handling."""

from __future__ import annotations

import pytest

from etymyriad.config import Config, redact_dsn


def test_redact_dsn_masks_password() -> None:
    """The password in a DSN is masked so it never reaches a log."""
    dsn = "postgresql://etymyriad:s3cret@db.neon.tech:5432/main"
    assert (
        redact_dsn(dsn) == "postgresql://etymyriad:***@db.neon.tech:5432/main"
    )


def test_redact_dsn_without_password_is_unchanged() -> None:
    """A DSN carrying no password passes through untouched."""
    dsn = "postgresql://etymyriad@localhost:5432/main"
    assert redact_dsn(dsn) == dsn


def _base_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://u@h/db")
    monkeypatch.setenv("WIKTEXTRACT_DUMP", "data/dump.jsonl")


def test_from_env_reads_dump_date(monkeypatch: pytest.MonkeyPatch) -> None:
    """Config carries the pinned dump date from the environment."""
    _base_env(monkeypatch)
    monkeypatch.setenv("WIKTEXTRACT_DUMP_DATE", "2026-06-01")
    assert Config.from_env().dump_date == "2026-06-01"


def test_from_env_requires_dump_date(monkeypatch: pytest.MonkeyPatch) -> None:
    """A missing dump date is fatal, since every source_ref pins it."""
    _base_env(monkeypatch)
    monkeypatch.delenv("WIKTEXTRACT_DUMP_DATE", raising=False)
    with pytest.raises(RuntimeError, match="WIKTEXTRACT_DUMP_DATE"):
        Config.from_env()
