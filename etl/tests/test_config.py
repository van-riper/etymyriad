"""Tests for configuration and DSN handling."""

from __future__ import annotations

from etymyriad.config import redact_dsn


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
