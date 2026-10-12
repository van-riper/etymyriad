"""Tests for configuration and DSN handling."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from etymyriad.config import (
    LOCAL_DATABASE_URL,
    Config,
    redact_dsn,
)

if TYPE_CHECKING:
    from pathlib import Path


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


def test_dump_date_has_no_default(monkeypatch: pytest.MonkeyPatch) -> None:
    """A missing dump date stays None instead of falling back."""
    monkeypatch.delenv("WIKTEXTRACT_DUMP_DATE", raising=False)
    assert Config.from_env().dump_date is None


@pytest.mark.parametrize(
    "value", ["2026-9-2", "20260902", "2026-13-01", "2026-W36-3"]
)
def test_dump_date_rejects_malformed_values(
    monkeypatch: pytest.MonkeyPatch, value: str
) -> None:
    """A dump date that isn't a real YYYY-MM-DD fails fast."""
    monkeypatch.setenv("WIKTEXTRACT_DUMP_DATE", value)
    with pytest.raises(ValueError, match="YYYY-MM-DD"):
        Config.from_env()


def test_from_env_defaults_database_url_to_local_postgres(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A missing DATABASE_URL falls back to the standard local dev DB."""
    _base_env(monkeypatch)
    monkeypatch.setenv("WIKTEXTRACT_DUMP_DATE", "2026-06-01")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    assert Config.from_env().database_url == LOCAL_DATABASE_URL


def test_from_env_defaults_dump_path_to_the_newest_filtered_dump(
    monkeypatch: pytest.MonkeyPatch, data_dir: Path
) -> None:
    """A missing WIKTEXTRACT_DUMP falls back to the newest stamped file."""
    data_dir.mkdir()
    for stamp in ("20260101T000000Z", "20260201T000000Z"):
        (data_dir / f"etymyriad-data-{stamp}.jsonl").touch()
    monkeypatch.delenv("WIKTEXTRACT_DUMP", raising=False)
    assert Config.from_env().dump_path == str(
        data_dir / "etymyriad-data-20260201T000000Z.jsonl"
    )


def test_dump_env_wins_over_the_newest_file(
    monkeypatch: pytest.MonkeyPatch, data_dir: Path
) -> None:
    """An explicit WIKTEXTRACT_DUMP beats any filtered file on disk."""
    data_dir.mkdir()
    (data_dir / "etymyriad-data-20260201T000000Z.jsonl").touch()
    monkeypatch.setenv("WIKTEXTRACT_DUMP", "data/dump.jsonl")
    assert Config.from_env().dump_path == "data/dump.jsonl"


def test_dump_path_is_none_without_a_dump(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No WIKTEXTRACT_DUMP and no filtered file leaves the path unset."""
    monkeypatch.delenv("WIKTEXTRACT_DUMP", raising=False)
    assert Config.from_env().dump_path is None


def test_repr_omits_database_url() -> None:
    """repr(Config) never echoes the raw DSN.

    A stray `print(config)` or an unhandled-exception traceback that
    captures local variables must not become a credential leak.
    """
    config = Config(
        database_url="postgresql://etymyriad:s3cret@db.neon.tech/main",
        dump_path="data/dump.jsonl",
        dump_date="2026-06-01",
    )
    assert "s3cret" not in repr(config)
    assert "dump.jsonl" in repr(config)
