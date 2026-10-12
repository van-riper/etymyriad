"""Tests for the ETL's on-disk file layout."""

from __future__ import annotations

import os
import re
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


_OLDER = "20260101T000000Z"
_NEWER = "20260201T000000Z"


def test_new_stamp_is_utc_basic_format() -> None:
    """A stamp is a UTC time in ISO 8601 basic format."""
    assert re.fullmatch(r"\d{8}T\d{6}Z", datafiles.new_stamp())


@pytest.mark.parametrize(
    ("name", "stamp"),
    [
        (f"etymyriad-data-{_OLDER}.jsonl", _OLDER),
        (f"etymyriad-edges-{_OLDER}.jsonl", None),
        (f"etymyriad-data-{_OLDER}.fields.json", None),
        (f"etymyriad-data-{_OLDER}.jsonl.tmp", None),
        ("etymyriad-data-2026-01-01.jsonl", None),
        ("indo-european.jsonl", None),
    ],
)
def test_stamp_of_reads_only_filtered_dump_names(
    name: str, stamp: str | None
) -> None:
    """Only a filtered dump's own name carries a stamp."""
    assert datafiles.stamp_of(f"/anywhere/{name}") == stamp


def test_modified_stamp_reads_the_mtime_in_utc(tmp_path: Path) -> None:
    """A file's modification time becomes a stamp in the same format."""
    path = tmp_path / "dump.jsonl"
    path.touch()
    os.utime(path, (1_760_000_000, 1_760_000_000))
    assert datafiles.modified_stamp(path) == "20251009T085320Z"


def test_modified_stamp_is_none_for_a_missing_file(tmp_path: Path) -> None:
    """A file that doesn't exist has no modification time to read."""
    assert datafiles.modified_stamp(tmp_path / "gone.jsonl") is None


def test_paths_land_in_the_data_dir(data_dir: Path) -> None:
    """Stamped paths sit flat in the data directory."""
    assert datafiles.data_path(_OLDER) == (
        data_dir / f"etymyriad-data-{_OLDER}.jsonl"
    )
    assert datafiles.edges_path(_OLDER) == (
        data_dir / f"etymyriad-edges-{_OLDER}.jsonl"
    )


def test_latest_file_picks_the_newest_name_per_prefix(data_dir: Path) -> None:
    """The newest stamp wins; temp files and odd names are ignored."""
    data_dir.mkdir()
    for name in (
        f"etymyriad-data-{_OLDER}.jsonl",
        f"etymyriad-data-{_NEWER}.jsonl.tmp",
        "etymyriad-data-zzz.jsonl",
        f"etymyriad-edges-{_NEWER}.jsonl",
    ):
        (data_dir / name).touch()
    assert datafiles.latest_file(data_dir, datafiles.DATA_PREFIX) == (
        data_dir / f"etymyriad-data-{_OLDER}.jsonl"
    )
    assert datafiles.latest_file(data_dir, datafiles.EDGES_PREFIX) == (
        data_dir / f"etymyriad-edges-{_NEWER}.jsonl"
    )


def test_latest_file_is_none_without_a_data_dir(data_dir: Path) -> None:
    """A fresh clone with no data/ has no latest file."""
    assert datafiles.latest_file(data_dir, datafiles.DATA_PREFIX) is None


def test_fields_round_trip_beside_the_data_file(tmp_path: Path) -> None:
    """A sidecar sits next to its data file and reads back as written."""
    data_file = tmp_path / f"etymyriad-data-{_OLDER}.jsonl"
    datafiles.write_fields(data_file, ["word", "senses.tags"])
    assert datafiles.fields_path(data_file).name == (
        f"etymyriad-data-{_OLDER}.fields.json"
    )
    assert datafiles.read_fields(data_file) == {"word", "senses.tags"}


def test_read_fields_is_none_without_a_sidecar(tmp_path: Path) -> None:
    """A dump with no sidecar reports none rather than raising."""
    assert datafiles.read_fields(tmp_path / "dump.jsonl") is None


def test_stale_files_keep_edge_files_newer_than_the_newest_dump(
    data_dir: Path,
) -> None:
    """An edge file stamped after the newest dump is not stale."""
    data_dir.mkdir()
    for name in (
        f"etymyriad-data-{_OLDER}.jsonl",
        f"etymyriad-edges-{_NEWER}.jsonl",
    ):
        (data_dir / name).touch()
    assert datafiles.stale_files(data_dir, None) == []
