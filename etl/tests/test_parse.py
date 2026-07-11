"""Tests for the JSONL streaming layer."""

from __future__ import annotations

import gzip
import logging
from typing import TYPE_CHECKING

from etymyriad.parse import stream_entries

if TYPE_CHECKING:
    from pathlib import Path

    import pytest


def _write(path: Path, *lines: str) -> Path:
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def test_stream_reads_gzip_dump(tmp_path: Path) -> None:
    """A .gz-suffixed dump is transparently decompressed."""
    dump = tmp_path / "dump.jsonl.gz"
    with gzip.open(dump, "wt", encoding="utf-8") as handle:
        handle.write('{"word": "alpha"}\n{"word": "beta"}\n')
    words = [entry["word"] for entry in stream_entries(dump)]
    assert words == ["alpha", "beta"]


def test_stream_skips_malformed_lines(tmp_path: Path) -> None:
    """A line that is not valid JSON is skipped, not fatal."""
    dump = _write(
        tmp_path / "dump.jsonl",
        '{"word": "alpha"}',
        "this is not json",
        '{"word": "beta"}',
    )
    words = [entry["word"] for entry in stream_entries(dump)]
    assert words == ["alpha", "beta"]


def test_stream_logs_malformed_line_number(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A skipped line is logged as a warning naming its line number."""
    dump = _write(
        tmp_path / "dump.jsonl",
        '{"word": "alpha"}',
        "this is not json",
    )
    with caplog.at_level(logging.WARNING):
        list(stream_entries(dump))
    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warnings) == 1
    assert "2" in warnings[0].getMessage()
