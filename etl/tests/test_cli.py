"""Tests for the command-line entry point."""

from __future__ import annotations

import json
import logging
import os
from collections import Counter
from typing import TYPE_CHECKING

import psycopg
import pytest

from etymyriad.__main__ import _fmt, _print_rel_type_breakdown, main
from etymyriad.edgefile import term_to_json, write_edges
from etymyriad.model import EtymEdge, RelType, Term

if TYPE_CHECKING:
    from collections.abc import Iterable
    from pathlib import Path

_FRIJAZ_ENTRY = (
    '{"word": "frijaz", "lang_code": "gem-pro", "pos": "adj", '
    '"senses": [{"glosses": ["free"]}], '
    '"etymology_templates": [{"name": "inh", "args": '
    '{"1": "gem-pro", "2": "ine-pro", "3": "*priH\\u00f3s"}}]}\n'
)
_INHERITED_EDGE = EtymEdge(
    src=Term("la", "aqua"),
    dst=Term("es", "agua"),
    rel_type=RelType.INHERITED,
    anchor="aqua",
)


def _stub_load_edges(
    monkeypatch: pytest.MonkeyPatch,
) -> list[tuple[list[EtymEdge | Term], dict[str, object]]]:
    """Replace the CLI's `load_edges` with a recorder.

    Returns:
        A list that gains one (consumed edges, kwargs) pair per call.
    """
    calls: list[tuple[list[EtymEdge | Term], dict[str, object]]] = []

    def _fake(
        _url: str, edges: Iterable[EtymEdge | Term], **kwargs: object
    ) -> int:
        consumed = list(edges)
        calls.append((consumed, kwargs))
        return len(consumed)

    monkeypatch.setattr("etymyriad.__main__.load_edges", _fake)
    return calls


def _set_env(
    monkeypatch: pytest.MonkeyPatch, dump: str = "/does/not/matter.jsonl"
) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://u@h/db")
    monkeypatch.setenv("WIKTEXTRACT_DUMP", dump)
    monkeypatch.setenv("WIKTEXTRACT_DUMP_DATE", "2026-06-01")


def test_fmt_uses_thousands_separators() -> None:
    """A large count reads as "10,287,531", not "10287531"."""
    assert _fmt(10_287_531) == "10,287,531"


def test_rel_type_breakdown_uses_thousands_separators(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The per-rel_type breakdown formats large counts with commas too."""
    _print_rel_type_breakdown(Counter({RelType.INHERITED: 2_993_290}))

    assert "inherited: 2,993,290" in capsys.readouterr().out


def test_load_failure_redacts_dsn_from_log(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A failed load logs its error without leaking the DSN password.

    Driver errors (e.g. a bad conninfo string) sometimes echo the DSN
    verbatim in their message; that must never reach a log unredacted.
    """
    dsn = "postgresql://etymyriad:s3cret@db.neon.tech/main"
    edges = tmp_path / "edges.jsonl"
    write_edges(edges, [])
    monkeypatch.setenv("DATABASE_URL", dsn)
    monkeypatch.setenv("WIKTEXTRACT_DUMP", "/does/not/matter.jsonl")
    monkeypatch.setenv("WIKTEXTRACT_DUMP_DATE", "2026-06-01")

    def _boom(*_args: object, **_kwargs: object) -> int:
        msg = f"connection failed: {dsn}"
        raise psycopg.OperationalError(msg)

    monkeypatch.setattr("etymyriad.__main__.load_edges", _boom)

    with caplog.at_level(logging.ERROR):
        code = main(["load", "--edges", str(edges)])

    assert code == 1
    assert "s3cret" not in caplog.text


def test_filter_ine_writes_only_indo_european_entries(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The filter-ine subcommand narrows a combined dump to IE languages."""
    dump = tmp_path / "combined.jsonl"
    dump.write_text(
        '{"word": "etymology", "lang_code": "en"}\n'
        '{"word": "水", "lang_code": "ja"}\n'
        '{"word": "aqua", "lang_code": "la"}\n',
        encoding="utf-8",
    )
    out = tmp_path / "indo-european.jsonl"
    monkeypatch.setenv("DATABASE_URL", "postgresql://u@h/db")
    monkeypatch.setenv("WIKTEXTRACT_DUMP", "/does/not/matter.jsonl")
    monkeypatch.setenv("WIKTEXTRACT_DUMP_DATE", "2026-06-01")

    code = main(["filter-ine", "--input", str(dump), "--output", str(out)])

    assert code == 0
    words = [json.loads(line)["word"] for line in out.read_text().splitlines()]
    assert words == ["etymology", "aqua"]


def test_normalize_writes_edge_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The normalize subcommand streams the dump and writes an edge file."""
    dump = tmp_path / "dump.jsonl"
    dump.write_text(
        '{"word": "etymology", "lang_code": "en"}\n', encoding="utf-8"
    )
    edges = tmp_path / "edges.jsonl"
    monkeypatch.setenv("DATABASE_URL", "postgresql://u@h/db")
    monkeypatch.setenv("WIKTEXTRACT_DUMP", str(dump))
    monkeypatch.setenv("WIKTEXTRACT_DUMP_DATE", "2026-06-01")

    code = main(["normalize", "--edges", str(edges)])

    assert code == 0
    assert edges.exists()


def test_load_passes_edges_and_dump_date_to_the_loader(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`load` streams the edge file into `load_edges` with the dump date."""
    calls = _stub_load_edges(monkeypatch)
    _set_env(monkeypatch)
    edges = tmp_path / "edges.jsonl"
    write_edges(edges, [_INHERITED_EDGE])

    assert main(["load", "--edges", str(edges)]) == 0

    assert calls == [
        ([_INHERITED_EDGE], {"dump_date": "2026-06-01", "check_drift": True})
    ]


def test_load_prints_rel_type_breakdown(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The load subcommand reports edge counts broken down by rel_type."""
    _stub_load_edges(monkeypatch)
    _set_env(monkeypatch)
    edges = tmp_path / "edges.jsonl"
    borrowed = EtymEdge(
        src=Term("en", "water"),
        dst=Term("de", "Wasser"),
        rel_type=RelType.BORROWED,
        anchor="water",
    )
    write_edges(edges, [_INHERITED_EDGE, _INHERITED_EDGE, borrowed])

    assert main(["load", "--edges", str(edges)]) == 0

    out = capsys.readouterr().out
    assert "inherited: 2" in out
    assert "borrowed: 1" in out


def test_load_requires_a_dump_date(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Without a dump date, `load` exits 2 before touching any file."""
    monkeypatch.delenv("WIKTEXTRACT_DUMP_DATE", raising=False)

    assert main(["load"]) == 2

    assert "WIKTEXTRACT_DUMP_DATE" in capsys.readouterr().err


def test_all_requires_a_dump_date(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Without a dump date, `all` exits 2 before parsing the dump."""
    monkeypatch.delenv("WIKTEXTRACT_DUMP_DATE", raising=False)

    assert main(["all"]) == 2

    assert "WIKTEXTRACT_DUMP_DATE" in capsys.readouterr().err


def test_malformed_dump_date_exits_2_for_any_command(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A bad WIKTEXTRACT_DUMP_DATE prints its message instead of a trace."""
    monkeypatch.setenv("WIKTEXTRACT_DUMP_DATE", "2026-13-01")

    assert main(["load"]) == 2

    assert "YYYY-MM-DD" in capsys.readouterr().err


@pytest.mark.parametrize(("argv", "level"), [(["--debug"], 10), ([], 20)])
def test_debug_flag_sets_the_root_log_level(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    argv: list[str],
    level: int,
) -> None:
    """--debug logs at DEBUG; otherwise INFO."""
    dump = tmp_path / "dump.jsonl"
    dump.write_text("", encoding="utf-8")
    _set_env(monkeypatch, str(dump))
    root = logging.getLogger()
    monkeypatch.setattr(root, "handlers", [])
    monkeypatch.setattr(root, "level", root.level)

    assert main([*argv, "parse"]) == 0

    assert root.level == level


def test_load_passes_the_gate_flag(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """--skip-sanity-gate turns the drift check off."""
    calls: list[dict[str, object]] = []
    monkeypatch.setenv("WIKTEXTRACT_DUMP_DATE", "2026-09-02")
    monkeypatch.setattr(
        "etymyriad.__main__.load_edges",
        lambda _url, _edges, **kwargs: calls.append(kwargs) or 1,
    )
    edges = tmp_path / "edges.jsonl"
    edges.write_text(term_to_json(Term("en", "a")) + "\n", encoding="utf-8")

    assert main(["load", "--edges", str(edges), "--skip-sanity-gate"]) == 0

    assert calls == [{"dump_date": "2026-09-02", "check_drift": False}]


def test_all_passes_the_gate_flag(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`all` forwards --skip-sanity-gate to the loader too."""
    calls = _stub_load_edges(monkeypatch)
    dump = tmp_path / "dump.jsonl"
    dump.write_text(_FRIJAZ_ENTRY, encoding="utf-8")
    _set_env(monkeypatch, str(dump))

    code = main([
        "all",
        "--edges",
        str(tmp_path / "e.jsonl"),
        "--skip-sanity-gate",
    ])

    assert code == 0
    assert [kwargs for _, kwargs in calls] == [
        {"dump_date": "2026-06-01", "check_drift": False}
    ]


def test_all_writes_edges_file_and_loads_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`all` persists the normalized edges, then loads them."""
    calls = _stub_load_edges(monkeypatch)
    dump = tmp_path / "dump.jsonl"
    dump.write_text(_FRIJAZ_ENTRY, encoding="utf-8")
    edges = tmp_path / "edges.jsonl"
    _set_env(monkeypatch, str(dump))

    code = main(["all", "--edges", str(edges)])

    assert code == 0
    assert edges.read_text().strip()
    assert calls[0][0]
    assert calls[0][1] == {"dump_date": "2026-06-01", "check_drift": True}


def test_all_skips_normalize_when_edges_file_is_fresh(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`all` reuses a fresh edges.jsonl instead of re-parsing the dump."""
    calls = _stub_load_edges(monkeypatch)
    dump = tmp_path / "dump.jsonl"
    dump.write_text("irrelevant: normalize must not run\n", encoding="utf-8")
    edges = tmp_path / "edges.jsonl"
    write_edges(edges, [_INHERITED_EDGE])
    os.utime(dump, (1_000, 1_000))
    os.utime(edges, (2_000, 2_000))

    def _boom(*_args: object, **_kwargs: object) -> object:
        msg = "normalize must not run when edges.jsonl is fresh"
        raise AssertionError(msg)

    monkeypatch.setattr("etymyriad.__main__.normalize", _boom)
    _set_env(monkeypatch, str(dump))

    assert main(["all", "--edges", str(edges)]) == 0

    assert calls[0][0] == [_INHERITED_EDGE]


def test_all_reparses_when_dump_is_newer_than_edges_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A dump touched after edges.jsonl was written forces a re-normalize."""
    calls = _stub_load_edges(monkeypatch)
    dump = tmp_path / "dump.jsonl"
    dump.write_text(_FRIJAZ_ENTRY, encoding="utf-8")
    edges = tmp_path / "edges.jsonl"
    write_edges(edges, [])
    os.utime(edges, (1_000, 1_000))
    os.utime(dump, (2_000, 2_000))
    _set_env(monkeypatch, str(dump))

    assert main(["all", "--edges", str(edges)]) == 0

    assert calls[0][0]


def test_all_force_normalize_reruns_even_when_fresh(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """--force-normalize re-parses the dump even over a fresh edges.jsonl."""
    calls = _stub_load_edges(monkeypatch)
    dump = tmp_path / "dump.jsonl"
    dump.write_text(_FRIJAZ_ENTRY, encoding="utf-8")
    edges = tmp_path / "edges.jsonl"
    write_edges(edges, [])
    os.utime(dump, (1_000, 1_000))
    os.utime(edges, (2_000, 2_000))
    _set_env(monkeypatch, str(dump))

    assert main(["all", "--edges", str(edges), "--force-normalize"]) == 0

    assert calls[0][0]


def test_sync_languages_writes_to_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """sync-languages hands its --output path to sync_snapshot."""
    written: list[Path] = []

    def _fake_sync(output: Path, _client: object) -> dict[str, dict]:
        written.append(output)
        return {"languages": {}, "families": {}, "varieties": {}}

    monkeypatch.setenv("DATABASE_URL", "postgresql://u@h/db")
    monkeypatch.setenv("WIKTEXTRACT_DUMP", "/does/not/matter.jsonl")
    monkeypatch.setenv("WIKTEXTRACT_DUMP_DATE", "2026-06-01")
    monkeypatch.setattr("etymyriad.__main__.sync_snapshot", _fake_sync)

    code = main(["sync-languages", "--output", str(tmp_path / "r.json")])

    assert code == 0
    assert written == [tmp_path / "r.json"]
