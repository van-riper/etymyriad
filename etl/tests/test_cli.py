"""Tests for the command-line entry point."""

from __future__ import annotations

import json
import logging
import os
from collections import Counter
from typing import TYPE_CHECKING

import psycopg
import pytest

from etymyriad import datafiles
from etymyriad.__main__ import _fmt, _print_rel_type_breakdown, main
from etymyriad.edgefile import item_to_json, write_edges
from etymyriad.model import EtymEdge, RelType, Term
from etymyriad.normalize import field_paths

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


def test_filter_writes_a_stamped_file_of_trimmed_entries(
    tmp_path: Path, data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`filter` keeps in-scope entries, trimmed, in a new stamped file."""
    dump = tmp_path / "combined.jsonl"
    dump.write_text(
        '{"word": "etymology", "lang_code": "en", "translations": []}\n'
        '{"word": "水", "lang_code": "ja"}\n'
        '{"word": "aqua", "lang_code": "la"}\n',
        encoding="utf-8",
    )
    _set_env(monkeypatch)

    assert main(["filter", "--input", str(dump)]) == 0

    sidecar, output = sorted(data_dir.iterdir())
    assert sidecar.name.endswith(".fields.json")
    assert json.loads(sidecar.read_text(encoding="utf-8")) == sorted(
        field_paths()
    )
    assert datafiles.stamp_of(output) is not None
    lines = output.read_text(encoding="utf-8").splitlines()
    assert [json.loads(line) for line in lines] == [
        {"word": "etymology", "lang_code": "en"},
        {"word": "aqua", "lang_code": "la"},
    ]


def test_filter_honours_an_explicit_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """--output overrides the stamped default."""
    dump = tmp_path / "combined.jsonl"
    dump.write_text('{"word": "aqua", "lang_code": "la"}\n', encoding="utf-8")
    out = tmp_path / "elsewhere" / "subset.jsonl"
    _set_env(monkeypatch)

    assert main(["filter", "--input", str(dump), "--output", str(out)]) == 0

    assert out.read_text(encoding="utf-8").strip()


def test_filter_ine_is_gone() -> None:
    """The old command name no longer parses."""
    with pytest.raises(SystemExit):
        main(["filter-ine", "--input", "x.jsonl"])


@pytest.mark.parametrize("command", ["parse", "normalize", "all", "crosscheck"])
def test_readers_exit_2_without_a_dump(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    command: str,
) -> None:
    """With no WIKTEXTRACT_DUMP and no filtered file, readers say so."""
    _set_env(monkeypatch)
    monkeypatch.delenv("WIKTEXTRACT_DUMP")

    assert main([command]) == 2

    assert "etymyriad filter" in capsys.readouterr().err


def test_parse_defaults_to_the_newest_filtered_dump(
    data_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Without WIKTEXTRACT_DUMP, readers take the newest stamped file."""
    data_dir.mkdir()
    (data_dir / "etymyriad-data-20260101T000000Z.jsonl").write_text(
        '{"word": "a", "lang_code": "en"}\n', encoding="utf-8"
    )
    (data_dir / "etymyriad-data-20260201T000000Z.jsonl").write_text(
        '{"word": "a", "lang_code": "en"}\n{"word": "b", "lang_code": "en"}\n',
        encoding="utf-8",
    )
    _set_env(monkeypatch)
    monkeypatch.delenv("WIKTEXTRACT_DUMP")

    assert main(["parse"]) == 0

    assert "parsed 2 entries" in capsys.readouterr().out


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
    edges.write_text(item_to_json(Term("en", "a")) + "\n", encoding="utf-8")

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


def test_all_reuses_an_existing_edge_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`all` reuses an existing edge file instead of re-parsing."""
    calls = _stub_load_edges(monkeypatch)
    dump = tmp_path / "dump.jsonl"
    dump.write_text("irrelevant: normalize must not run\n", encoding="utf-8")
    edges = tmp_path / "edges.jsonl"
    write_edges(edges, [_INHERITED_EDGE])

    def _boom(*_args: object, **_kwargs: object) -> object:
        msg = "normalize must not run when the edge file exists"
        raise AssertionError(msg)

    monkeypatch.setattr("etymyriad.__main__.normalize", _boom)
    _set_env(monkeypatch, str(dump))

    assert main(["all", "--edges", str(edges)]) == 0

    assert calls[0][0] == [_INHERITED_EDGE]


def test_all_force_normalize_rebuilds_an_existing_edge_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """--force-normalize re-parses the dump even over an existing edge file."""
    calls = _stub_load_edges(monkeypatch)
    dump = tmp_path / "dump.jsonl"
    dump.write_text(_FRIJAZ_ENTRY, encoding="utf-8")
    edges = tmp_path / "edges.jsonl"
    write_edges(edges, [])
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


def test_crosscheck_reports_tree_edges_the_graph_lacks(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Each tree edge absent from the edge file is listed and counted."""
    dump = tmp_path / "dump.jsonl"
    dump.write_text(
        json.dumps({
            "word": "wine",
            "lang_code": "en",
            "etymology_templates": [
                {"name": "etymon", "args": {"2": ":inh", "tree": "1"}}
            ],
        })
        + "\n"
        + json.dumps({"word": "water", "lang_code": "en"})
        + "\n",
        encoding="utf-8",
    )
    edges = tmp_path / "edges.jsonl"
    write_edges(
        edges,
        [
            EtymEdge(
                src=Term("enm", "wyn"),
                dst=Term("en", "wine"),
                rel_type=RelType.INHERITED,
                anchor="a",
            )
        ],
    )
    tree = {
        "lang": "en",
        "term": "wine",
        "children": [
            {
                "keyword": "inherited",
                "terms": [
                    {
                        "lang": "enm",
                        "term": "wyn",
                        "children": [
                            {
                                "keyword": "inherited",
                                "terms": [
                                    {
                                        "lang": "ang",
                                        "term": "wīn",
                                        "children": [],
                                    }
                                ],
                            }
                        ],
                    }
                ],
            }
        ],
    }
    monkeypatch.setattr("etymyriad.__main__.fetch_tree", lambda *_args: tree)
    _set_env(monkeypatch, str(dump))

    exit_code = main(["crosscheck", "--edges", str(edges), "--limit", "5"])

    assert exit_code == 0
    out = capsys.readouterr().out
    assert "wine (en): ang:wīn -> enm:wyn (inherited)" in out
    assert "checked 1 trees: 2 edges, 1 missing" in out


def test_crosscheck_requires_the_dump_date(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Trees are pinned to the dump's date, so the run needs it set."""
    _set_env(monkeypatch)
    monkeypatch.delenv("WIKTEXTRACT_DUMP_DATE")

    exit_code = main(["crosscheck", "--edges", str(tmp_path / "e.jsonl")])

    assert exit_code == 2
    assert "WIKTEXTRACT_DUMP_DATE" in capsys.readouterr().err


def test_crosscheck_fetches_trees_as_of_the_dump_date(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The dump date reaches every tree fetch."""
    dump = tmp_path / "dump.jsonl"
    dump.write_text(
        json.dumps({
            "word": "wine",
            "lang_code": "en",
            "etymology_templates": [
                {"name": "etymon", "args": {"2": ":inh", "tree": "1"}}
            ],
        })
        + "\n",
        encoding="utf-8",
    )
    edges = tmp_path / "edges.jsonl"
    write_edges(edges, [])
    dates: list[str] = []

    def _fake_fetch(
        _client: object, _headword: str, _lang: str, dump_date: str
    ) -> None:
        dates.append(dump_date)

    monkeypatch.setattr("etymyriad.__main__.fetch_tree", _fake_fetch)
    _set_env(monkeypatch, str(dump))

    main(["crosscheck", "--edges", str(edges)])

    assert dates == ["2026-06-01"]


_STAMP = "20261011T143000Z"


def test_normalize_stamps_its_edge_file_from_the_dump(
    data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A filtered dump's stamp carries over to its edge file."""
    _stamped_dump(data_dir, field_paths())
    _set_env(monkeypatch)
    monkeypatch.delenv("WIKTEXTRACT_DUMP")

    assert main(["normalize"]) == 0

    assert (data_dir / f"etymyriad-edges-{_STAMP}.jsonl").read_text().strip()


def test_normalize_stamps_an_unstamped_dump_by_its_modification_time(
    tmp_path: Path, data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A dump with no stamp in its name lends its mtime instead."""
    dump = tmp_path / "dump.jsonl"
    dump.write_text(_FRIJAZ_ENTRY, encoding="utf-8")
    os.utime(dump, (1_760_000_000, 1_760_000_000))
    _set_env(monkeypatch, str(dump))

    assert main(["normalize"]) == 0

    assert [path.name for path in data_dir.iterdir()] == [
        "etymyriad-edges-20251009T085320Z.jsonl"
    ]


def test_all_reuses_the_edge_file_of_an_unstamped_dump(
    tmp_path: Path, data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An unchanged unstamped dump maps to the same edge file every run."""
    calls = _stub_load_edges(monkeypatch)
    dump = tmp_path / "dump.jsonl"
    dump.write_text("irrelevant: normalize must not run\n", encoding="utf-8")
    os.utime(dump, (1_760_000_000, 1_760_000_000))
    write_edges(
        data_dir / "etymyriad-edges-20251009T085320Z.jsonl", [_INHERITED_EDGE]
    )

    def _boom(*_args: object, **_kwargs: object) -> object:
        msg = "normalize must not run when the edge file exists"
        raise AssertionError(msg)

    monkeypatch.setattr("etymyriad.__main__.normalize", _boom)
    _set_env(monkeypatch, str(dump))

    assert main(["all"]) == 0

    assert calls[0][0] == [_INHERITED_EDGE]


def test_load_defaults_to_the_dumps_edge_file(
    data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`load` reads the edge file of the dump, not a newer stray one."""
    calls = _stub_load_edges(monkeypatch)
    _stamped_dump(data_dir, field_paths())
    write_edges(data_dir / f"etymyriad-edges-{_STAMP}.jsonl", [_INHERITED_EDGE])
    write_edges(data_dir / "etymyriad-edges-20261101T000000Z.jsonl", [])
    _set_env(monkeypatch)
    monkeypatch.delenv("WIKTEXTRACT_DUMP")

    assert main(["load"]) == 0

    assert calls[0][0] == [_INHERITED_EDGE]


def test_load_reads_the_edge_file_of_an_unstamped_dump(
    tmp_path: Path, data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An unstamped dump's edge file wins over newer-stamped ones."""
    calls = _stub_load_edges(monkeypatch)
    dump = tmp_path / "dump.jsonl"
    dump.write_text(_FRIJAZ_ENTRY, encoding="utf-8")
    os.utime(dump, (1_760_000_000, 1_760_000_000))
    write_edges(
        data_dir / "etymyriad-edges-20251009T085320Z.jsonl", [_INHERITED_EDGE]
    )
    write_edges(data_dir / f"etymyriad-edges-{_STAMP}.jsonl", [])
    _set_env(monkeypatch, str(dump))

    assert main(["load"]) == 0

    assert calls[0][0] == [_INHERITED_EDGE]


def test_load_refuses_another_dumps_edge_file(
    data_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A dump not yet normalized sends the user to normalize first."""
    _stub_load_edges(monkeypatch)
    _stamped_dump(data_dir, field_paths())
    write_edges(data_dir / "etymyriad-edges-20260101T000000Z.jsonl", [])
    _set_env(monkeypatch)
    monkeypatch.delenv("WIKTEXTRACT_DUMP")

    assert main(["load"]) == 2

    assert "etymyriad normalize" in capsys.readouterr().err


def test_load_without_a_dump_reads_the_newest_edge_file(
    data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """With no dump to match, `load` falls back to the newest edge file."""
    calls = _stub_load_edges(monkeypatch)
    write_edges(data_dir / "etymyriad-edges-20260101T000000Z.jsonl", [])
    write_edges(
        data_dir / "etymyriad-edges-20260201T000000Z.jsonl", [_INHERITED_EDGE]
    )
    _set_env(monkeypatch)
    monkeypatch.delenv("WIKTEXTRACT_DUMP")

    assert main(["load"]) == 0

    assert calls[0][0] == [_INHERITED_EDGE]


@pytest.mark.parametrize("command", ["load", "crosscheck"])
def test_edge_readers_exit_2_without_an_edge_file(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    command: str,
) -> None:
    """With no --edges and no edge file, the command says how to fix it."""
    _set_env(monkeypatch)

    assert main([command]) == 2

    assert "etymyriad normalize" in capsys.readouterr().err


def test_all_normalizes_into_the_dump_stamped_edge_file(
    data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`all` with no edge file for the dump's stamp normalizes first."""
    calls = _stub_load_edges(monkeypatch)
    _stamped_dump(data_dir, field_paths())
    write_edges(data_dir / "etymyriad-edges-20260101T000000Z.jsonl", [])
    _set_env(monkeypatch)
    monkeypatch.delenv("WIKTEXTRACT_DUMP")

    assert main(["all"]) == 0

    assert (data_dir / f"etymyriad-edges-{_STAMP}.jsonl").is_file()
    assert calls[0][0]


def _stamped_dump(data_dir: Path, fields: Iterable[str] | None) -> Path:
    """Write a one-entry stamped dump, with a sidecar unless fields is None.

    Returns:
        The dump's path.
    """
    data_dir.mkdir(exist_ok=True)
    dump = data_dir / f"etymyriad-data-{_STAMP}.jsonl"
    dump.write_text(_FRIJAZ_ENTRY, encoding="utf-8")
    if fields is not None:
        datafiles.write_fields(dump, fields)
    return dump


def test_normalize_refuses_a_stamped_dump_without_a_sidecar(
    data_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A trimmed dump whose kept fields are unknown is not read."""
    _set_env(monkeypatch, str(_stamped_dump(data_dir, None)))

    assert main(["normalize"]) == 2

    assert "re-run `etymyriad filter`" in capsys.readouterr().err


def test_normalize_refuses_a_dump_missing_a_parsed_field(
    data_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A dump filtered before the parser read a field names that field."""
    kept = field_paths() - {"senses.form_of.word"}
    _set_env(monkeypatch, str(_stamped_dump(data_dir, kept)))

    assert main(["normalize"]) == 2

    assert "senses.form_of.word" in capsys.readouterr().err


def test_normalize_accepts_a_sidecar_with_retired_fields(
    data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Fields the models no longer declare cost bytes, not edges."""
    kept = field_paths() | {"retired_field"}
    _set_env(monkeypatch, str(_stamped_dump(data_dir, kept)))

    assert main(["normalize"]) == 0


def test_guard_checks_an_unstamped_dump_with_a_sidecar(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A `filter --output` file is checked by its sidecar too."""
    dump = tmp_path / "subset.jsonl"
    dump.write_text(_FRIJAZ_ENTRY, encoding="utf-8")
    datafiles.write_fields(dump, ["word"])
    _set_env(monkeypatch, str(dump))

    assert main(["normalize"]) == 2


def test_guard_leaves_a_missing_dump_to_stream_entries(
    data_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A stamped dump that doesn't exist reports not found, not a sidecar."""
    missing = data_dir / "etymyriad-data-20261011T143000Z.jsonl"
    _set_env(monkeypatch, str(missing))

    with caplog.at_level(logging.ERROR):
        assert main(["normalize"]) == 1

    assert "not found" in caplog.text


_OLD, _MID, _NEW = (
    "20260101T000000Z",
    "20260201T000000Z",
    "20260301T000000Z",
)


def _group_names(stamp: str) -> list[str]:
    return [
        f"etymyriad-data-{stamp}.jsonl",
        f"etymyriad-data-{stamp}.fields.json",
        f"etymyriad-edges-{stamp}.jsonl",
    ]


def _fill_data_dir(data_dir: Path) -> None:
    """Write three stamp groups, a raw dump, and a leftover temp file."""
    data_dir.mkdir()
    names = [
        *_group_names(_OLD),
        *_group_names(_MID),
        *_group_names(_NEW),
        "raw-wiktextract-data.jsonl.gz",
        f"etymyriad-data-{_OLD}.jsonl.tmp",
    ]
    for name in names:
        (data_dir / name).write_bytes(b"x")


def test_prune_keeps_only_the_newest_group(
    data_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Older stamp groups go; the raw dump and temp files stay."""
    _fill_data_dir(data_dir)
    monkeypatch.delenv("WIKTEXTRACT_DUMP", raising=False)

    assert main(["prune"]) == 0

    assert sorted(path.name for path in data_dir.iterdir()) == sorted([
        *_group_names(_NEW),
        "raw-wiktextract-data.jsonl.gz",
        f"etymyriad-data-{_OLD}.jsonl.tmp",
    ])
    out = capsys.readouterr().out
    assert f"deleted etymyriad-edges-{_MID}.jsonl" in out
    assert "freed" in out


def test_prune_spares_the_group_wiktextract_dump_names(
    data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An older group still named by WIKTEXTRACT_DUMP is kept."""
    _fill_data_dir(data_dir)
    monkeypatch.setenv(
        "WIKTEXTRACT_DUMP", str(data_dir / f"etymyriad-data-{_OLD}.jsonl")
    )

    assert main(["prune"]) == 0

    remaining = {path.name for path in data_dir.iterdir()}
    assert set(_group_names(_OLD)) <= remaining
    assert not set(_group_names(_MID)) & remaining


def test_prune_without_a_filtered_dump_deletes_nothing(
    data_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """With no filtered dump to anchor on, prune leaves data/ alone."""
    data_dir.mkdir()
    (data_dir / f"etymyriad-edges-{_OLD}.jsonl").write_bytes(b"x")
    monkeypatch.delenv("WIKTEXTRACT_DUMP", raising=False)

    assert main(["prune"]) == 0

    assert [path.name for path in data_dir.iterdir()] == [
        f"etymyriad-edges-{_OLD}.jsonl"
    ]
    assert "nothing to prune" in capsys.readouterr().out


def test_prune_without_a_data_dir_deletes_nothing(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A fresh clone with no data/ prunes nothing and says so."""
    monkeypatch.delenv("WIKTEXTRACT_DUMP", raising=False)

    assert main(["prune"]) == 0

    assert "nothing to prune" in capsys.readouterr().out


def test_normalize_reports_a_missing_unstamped_dump(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A dump with no stamp and no mtime to read still says not found."""
    _set_env(monkeypatch, str(tmp_path / "gone.jsonl"))

    with caplog.at_level(logging.ERROR):
        assert main(["normalize"]) == 1

    assert "not found" in caplog.text
