"""Tests for configuration and DSN handling."""

from __future__ import annotations

from typing import TYPE_CHECKING

from etymyriad.config import (
    LOCAL_DATABASE_URL,
    Config,
    redact_dsn,
)

if TYPE_CHECKING:
    from pathlib import Path

    import pytest


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


def test_from_env_defaults_database_url_to_local_postgres(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A missing DATABASE_URL falls back to the standard local dev DB."""
    _base_env(monkeypatch)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    assert Config.from_env().database_url == LOCAL_DATABASE_URL


def test_from_env_defaults_dump_path_to_the_filtered_dump(
    data_dir: Path,
) -> None:
    """Config finds the filtered dump."""
    data_dir.mkdir()
    (data_dir / "etymyriad-data.jsonl").touch()
    assert Config.from_env().dump_path == str(data_dir / "etymyriad-data.jsonl")


def test_dump_env_is_ignored(
    monkeypatch: pytest.MonkeyPatch, data_dir: Path
) -> None:
    """Readers take the filtered dump, whatever WIKTEXTRACT_DUMP says."""
    data_dir.mkdir()
    (data_dir / "etymyriad-data.jsonl").touch()
    monkeypatch.setenv("WIKTEXTRACT_DUMP", "data/dump.jsonl")
    assert Config.from_env().dump_path == str(data_dir / "etymyriad-data.jsonl")


def test_dump_path_is_none_without_a_dump() -> None:
    """No filtered file leaves the path unset."""
    assert Config.from_env().dump_path is None


def test_repr_omits_database_url() -> None:
    """repr(Config) never echoes the raw DSN.

    A stray `print(config)` or an unhandled-exception traceback that
    captures local variables must not become a credential leak.
    """
    config = Config(
        database_url="postgresql://etymyriad:s3cret@db.neon.tech/main",
        dump_path="data/dump.jsonl",
    )
    assert "s3cret" not in repr(config)
    assert "dump.jsonl" in repr(config)
