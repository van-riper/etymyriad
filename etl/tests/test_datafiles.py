"""Tests for the ETL's on-disk file layout."""

from __future__ import annotations

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
