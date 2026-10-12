"""Tests for the ETL's on-disk file layout."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

import pytest

from etymyriad import datafiles

if TYPE_CHECKING:
    from pathlib import Path


def test_staged_path_renames_onto_the_target(tmp_path: Path) -> None:
    """A clean block leaves only the finished file, created dirs included."""
    target = tmp_path / "new" / "out.jsonl"
    with datafiles.staged_path(target) as staged:
        staged.write_text("done\n", encoding="utf-8")
    assert target.read_text(encoding="utf-8") == "done\n"
    assert sorted(path.name for path in target.parent.iterdir()) == [
        "out.jsonl"
    ]


@pytest.mark.parametrize("error", [RuntimeError, KeyboardInterrupt])
def test_staged_path_leaves_nothing_when_the_block_raises(
    tmp_path: Path, error: type[BaseException]
) -> None:
    """A failed or interrupted write leaves no temp or target file."""
    target = tmp_path / "out.jsonl"

    def _write_then_fail() -> None:
        with datafiles.staged_path(target) as staged:
            staged.write_text("partial", encoding="utf-8")
            raise error

    with pytest.raises(error):
        _write_then_fail()
    assert list(tmp_path.iterdir()) == []


def test_paths_are_fixed_names_in_the_data_dir(data_dir: Path) -> None:
    """The filtered dump and the edge file each have one home."""
    assert datafiles.data_path() == data_dir / "etymyriad-data.jsonl"
    assert datafiles.edges_path() == data_dir / "etymyriad-edges.jsonl"


def test_fields_round_trip_beside_the_data_file(tmp_path: Path) -> None:
    """A sidecar sits next to its data file and reads back as written."""
    data_file = tmp_path / "etymyriad-data.jsonl"
    datafiles.write_fields(data_file, ["word", "senses.tags"])
    assert datafiles.fields_path(data_file).name == (
        "etymyriad-data.fields.json"
    )
    assert datafiles.read_fields(data_file) == {"word", "senses.tags"}


def test_read_fields_is_none_without_a_sidecar(tmp_path: Path) -> None:
    """A dump with no sidecar reports none rather than raising."""
    assert datafiles.read_fields(tmp_path / "dump.jsonl") is None


def _touch_at(path: Path, seconds: int) -> Path:
    path.touch()
    os.utime(path, (seconds, seconds))
    return path


@pytest.mark.parametrize("edges_seconds", [2_000, 1_000])
def test_is_current_when_the_edge_file_is_no_older(
    tmp_path: Path, edges_seconds: int
) -> None:
    """An edge file written at or after its dump is current."""
    dump = _touch_at(tmp_path / "dump.jsonl", 1_000)
    edges = _touch_at(tmp_path / "edges.jsonl", edges_seconds)
    assert datafiles.is_current(edges, dump)


def test_is_not_current_when_the_dump_is_newer(tmp_path: Path) -> None:
    """A dump rewritten after its edge file makes the edge file stale."""
    dump = _touch_at(tmp_path / "dump.jsonl", 1_000)
    edges = _touch_at(tmp_path / "edges.jsonl", 999)
    assert not datafiles.is_current(edges, dump)


def test_is_current_is_false_for_a_missing_edge_file(tmp_path: Path) -> None:
    """An edge file that doesn't exist can't be current."""
    dump = _touch_at(tmp_path / "dump.jsonl", 1_000)
    assert not datafiles.is_current(tmp_path / "gone.jsonl", dump)


def test_raw_dump_path_names_the_dump_date(data_dir: Path) -> None:
    """The raw dump's file name carries the date of the dump it holds."""
    assert datafiles.raw_dump_path("2026-09-02") == (
        data_dir / "wiktextract-data-2026-09-02.jsonl.gz"
    )


def test_local_dump_date_is_none_without_a_raw_dump(data_dir: Path) -> None:
    """A missing data directory or no raw dump in it means nothing local."""
    assert datafiles.local_dump_date() is None
    data_dir.mkdir()
    (data_dir / "etymyriad-data.jsonl").write_text("", encoding="utf-8")
    assert datafiles.local_dump_date() is None


def test_local_dump_date_picks_the_newest_raw_dump(data_dir: Path) -> None:
    """With several raw dumps on disk, the latest date wins."""
    data_dir.mkdir()
    for dump_date in ("2026-06-01", "2026-09-02", "2026-07-15"):
        datafiles.raw_dump_path(dump_date).write_bytes(b"")

    assert datafiles.local_dump_date() == "2026-09-02"
