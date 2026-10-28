"""Tests for the command-line entry point."""

from __future__ import annotations

import gzip
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
_SERVED_DUMP_DATE = "2026-06-01"
_AQUA_ENTRY = '{"word": "aqua", "lang_code": "la"}\n'


@pytest.fixture
def downloads() -> list[Path]:
    """Record the raw dumps the CLI "downloads".

    Returns:
        A list that gains the destination of each download.
    """
    return []


@pytest.fixture(autouse=True)
def _offline_kaikki(
    monkeypatch: pytest.MonkeyPatch, downloads: list[Path]
) -> None:
    """Answer the CLI's kaikki.org lookups without the network."""
    monkeypatch.setattr(
        "etymyriad.__main__.served_dump_date",
        lambda _client: _SERVED_DUMP_DATE,
    )

    def _download(_client: object, destination: Path) -> None:
        downloads.append(destination)
        destination.parent.mkdir(exist_ok=True)
        destination.write_bytes(gzip.compress(_AQUA_ENTRY.encode()))

    monkeypatch.setattr("etymyriad.__main__.download_raw_dump", _download)


@pytest.fixture
def local_raw_dump(data_dir: Path) -> Path:
    """Put the raw dump that dates citations on disk.

    Returns:
        The raw dump's path, dated like the page the CLI stubs serve.
    """
    data_dir.mkdir(exist_ok=True)
    raw = datafiles.raw_dump_path(_SERVED_DUMP_DATE)
    raw.write_bytes(b"")
    return raw


def _no_dump_date(_client: object) -> str:
    """Stand in for a kaikki.org page that names no dump date.

    Raises:
        ValueError: Always, as `served_dump_date` does for such a page.
    """
    msg = "https://kaikki.org/dictionary/rawdata.html names no dump date"
    raise ValueError(msg)


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


def _set_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://u@h/db")


def test_fmt_uses_thousands_separators() -> None:
    """A large count reads as "10,287,531", not "10287531"."""
    assert _fmt(10_287_531) == "10,287,531"


def test_rel_type_breakdown_uses_thousands_separators(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The per-rel_type breakdown formats large counts with commas too."""
    _print_rel_type_breakdown(Counter({RelType.INHERITED: 2_993_290}))

    assert "inherited: 2,993,290" in capsys.readouterr().out


@pytest.mark.usefixtures("local_raw_dump")
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

    def _boom(*_args: object, **_kwargs: object) -> int:
        msg = f"connection failed: {dsn}"
        raise psycopg.OperationalError(msg)

    monkeypatch.setattr("etymyriad.__main__.load_edges", _boom)

    with caplog.at_level(logging.ERROR):
        code = main(["load", "--edges", str(edges)])

    assert code == 1
    assert "s3cret" not in caplog.text


def test_filter_writes_the_default_file_of_trimmed_entries(
    tmp_path: Path, data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`filter` keeps in-scope entries, trimmed, in the default file."""
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
    assert output == data_dir / "etymyriad-data.jsonl"
    lines = output.read_text(encoding="utf-8").splitlines()
    assert [json.loads(line) for line in lines] == [
        {"word": "etymology", "lang_code": "en"},
        {"word": "aqua", "lang_code": "la"},
    ]


def test_filter_has_no_output_flag(
    tmp_path: Path, data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Readers take only the default file, so filter writes only there."""
    dump = tmp_path / "combined.jsonl"
    dump.write_text('{"word": "aqua", "lang_code": "la"}\n', encoding="utf-8")
    out = tmp_path / "elsewhere.jsonl"
    _set_env(monkeypatch)

    with pytest.raises(SystemExit) as exit_info:
        main(["filter", "--input", str(dump), "--output", str(out)])

    assert exit_info.value.code == 2
    assert not out.exists()
    assert not data_dir.exists()


def test_filter_can_refilter_the_filtered_dump_in_place(
    data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """With one output path, re-filtering reads, then replaces, the file."""
    dump = _filtered_dump(data_dir, field_paths())
    _set_env(monkeypatch)

    assert main(["filter", "--input", str(dump)]) == 0

    lines = dump.read_text(encoding="utf-8").splitlines()
    assert [json.loads(line)["word"] for line in lines] == ["frijaz"]


def test_filter_ine_is_gone() -> None:
    """The old command name no longer parses."""
    with pytest.raises(SystemExit):
        main(["filter-ine", "--input", "x.jsonl"])


@pytest.mark.parametrize("command", ["parse", "normalize", "crosscheck"])
def test_readers_exit_2_without_a_dump(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    command: str,
) -> None:
    """With no filtered file, readers say how to make one."""
    _set_env(monkeypatch)

    assert main([command]) == 2

    err = capsys.readouterr().err
    assert "etymyriad filter" in err
    assert "WIKTEXTRACT_DUMP" not in err


def test_parse_defaults_to_the_filtered_dump(
    data_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Readers take data/etymyriad-data.jsonl."""
    data_dir.mkdir()
    (data_dir / "etymyriad-data.jsonl").write_text(
        '{"word": "a", "lang_code": "en"}\n{"word": "b", "lang_code": "en"}\n',
        encoding="utf-8",
    )
    _set_env(monkeypatch)

    assert main(["parse"]) == 0

    assert "parsed 2 entries" in capsys.readouterr().out


def test_readers_ignore_wiktextract_dump(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Pointing the env at an unfiltered dump no longer skips filter."""
    raw = tmp_path / "raw-wiktextract-data.jsonl"
    raw.write_text('{"word": "水", "lang_code": "ja"}\n', encoding="utf-8")
    _set_env(monkeypatch)
    monkeypatch.setenv("WIKTEXTRACT_DUMP", str(raw))

    assert main(["parse"]) == 2

    assert "etymyriad filter" in capsys.readouterr().err


def test_normalize_writes_edge_file(
    tmp_path: Path,
    data_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The normalize subcommand streams the dump and writes an edge file."""
    _filtered_dump(
        data_dir, field_paths(), '{"word": "etymology", "lang_code": "en"}\n'
    )
    edges = tmp_path / "edges.jsonl"
    _set_env(monkeypatch)

    code = main(["normalize", "--edges", str(edges)])

    assert code == 0
    assert edges.exists()


@pytest.mark.usefixtures("local_raw_dump")
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


@pytest.mark.usefixtures("local_raw_dump")
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


@pytest.mark.usefixtures("local_raw_dump")
def test_load_reports_merged_edges_against_staged_edges(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The total is the loader's edge count, not every staged item."""

    def _fake(_url: str, items: Iterable[object], **_kwargs: object) -> int:
        list(items)
        return 1

    monkeypatch.setattr("etymyriad.__main__.load_edges", _fake)
    _set_env(monkeypatch)
    edges = tmp_path / "edges.jsonl"
    write_edges(edges, [_INHERITED_EDGE, _INHERITED_EDGE, Term("en", "con")])

    assert main(["load", "--edges", str(edges)]) == 0

    assert "loaded 1 edges from 2 staged" in capsys.readouterr().out


def test_load_cites_the_local_raw_dump_date(
    tmp_path: Path,
    data_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The raw dump's file name dates the citations, with no network."""
    calls = _stub_load_edges(monkeypatch)
    _set_env(monkeypatch)
    monkeypatch.setenv("WIKTEXTRACT_DUMP_DATE", "2001-01-01")
    monkeypatch.setattr("etymyriad.__main__.served_dump_date", _no_dump_date)
    data_dir.mkdir()
    datafiles.raw_dump_path("2026-09-02").write_bytes(b"")
    edges = tmp_path / "edges.jsonl"
    write_edges(edges, [_INHERITED_EDGE])

    with caplog.at_level(logging.INFO):
        assert main(["load", "--edges", str(edges)]) == 0

    assert [kwargs for _, kwargs in calls] == [
        {"dump_date": "2026-09-02", "check_drift": True}
    ]
    assert "dated 2026-09-02" in caplog.text


def test_load_exits_1_before_loading_without_a_raw_dump(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """With no raw dump to name a date, `load` stops before Postgres."""
    calls = _stub_load_edges(monkeypatch)
    _set_env(monkeypatch)
    edges = tmp_path / "edges.jsonl"
    write_edges(edges, [_INHERITED_EDGE])

    with caplog.at_level(logging.ERROR):
        assert main(["load", "--edges", str(edges)]) == 1

    assert calls == []
    assert "fetch-dump" in caplog.text


def test_all_reads_the_dump_date_before_normalizing(
    tmp_path: Path, data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Offline, `all` fails fast instead of after a long normalize."""
    _stub_load_edges(monkeypatch)
    _filtered_dump(data_dir, field_paths())
    _set_env(monkeypatch)
    monkeypatch.setattr("etymyriad.__main__.served_dump_date", _no_dump_date)
    edges = tmp_path / "e.jsonl"

    assert main(["all", "--edges", str(edges)]) == 1

    assert not edges.exists()


def test_normalize_never_reads_the_dump_date(
    tmp_path: Path, data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Commands that cite nothing run without the network."""
    _filtered_dump(
        data_dir, field_paths(), '{"word": "etymology", "lang_code": "en"}\n'
    )
    _set_env(monkeypatch)
    monkeypatch.setattr("etymyriad.__main__.served_dump_date", _no_dump_date)

    assert main(["normalize", "--edges", str(tmp_path / "e.jsonl")]) == 0


@pytest.mark.parametrize(("argv", "level"), [(["--debug"], 10), ([], 20)])
def test_debug_flag_sets_the_root_log_level(
    data_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
    argv: list[str],
    level: int,
) -> None:
    """--debug logs at DEBUG; otherwise INFO."""
    _filtered_dump(data_dir, field_paths(), "")
    _set_env(monkeypatch)
    root = logging.getLogger()
    monkeypatch.setattr(root, "handlers", [])
    monkeypatch.setattr(root, "level", root.level)

    assert main([*argv, "parse"]) == 0

    assert root.level == level


@pytest.mark.usefixtures("local_raw_dump")
def test_load_passes_the_gate_flag(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """--skip-sanity-gate turns the drift check off."""
    calls: list[dict[str, object]] = []
    monkeypatch.setattr(
        "etymyriad.__main__.load_edges",
        lambda _url, _edges, **kwargs: calls.append(kwargs) or 1,
    )
    edges = tmp_path / "edges.jsonl"
    edges.write_text(item_to_json(Term("en", "a")) + "\n", encoding="utf-8")

    assert main(["load", "--edges", str(edges), "--skip-sanity-gate"]) == 0

    assert calls == [{"dump_date": _SERVED_DUMP_DATE, "check_drift": False}]


def test_all_passes_the_gate_flag(
    tmp_path: Path, data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`all` forwards --skip-sanity-gate to the loader too."""
    calls = _stub_load_edges(monkeypatch)
    _filtered_dump(data_dir, field_paths())
    _set_env(monkeypatch)

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
    tmp_path: Path, data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`all` persists the normalized edges, then loads them."""
    calls = _stub_load_edges(monkeypatch)
    _filtered_dump(data_dir, field_paths())
    edges = tmp_path / "edges.jsonl"
    _set_env(monkeypatch)

    code = main(["all", "--edges", str(edges)])

    assert code == 0
    assert edges.read_text().strip()
    assert calls[0][0]
    assert calls[0][1] == {"dump_date": "2026-06-01", "check_drift": True}


def test_fetch_dump_downloads_and_prints_the_path(
    downloads: list[Path],
    capsys: pytest.CaptureFixture[str],
) -> None:
    """With nothing local, `fetch-dump` downloads and names the file."""
    assert main(["fetch-dump"]) == 0

    raw = datafiles.raw_dump_path(_SERVED_DUMP_DATE)
    assert downloads == [raw]
    assert capsys.readouterr().out.strip() == str(raw)


def test_fetch_dump_keeps_a_current_local_dump(
    downloads: list[Path],
    data_dir: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A local dump dated like the page is not downloaded again."""
    data_dir.mkdir()
    raw = datafiles.raw_dump_path(_SERVED_DUMP_DATE)
    raw.write_bytes(b"")

    assert main(["fetch-dump"]) == 0

    assert downloads == []
    assert capsys.readouterr().out.strip() == str(raw)


def test_fetch_dump_fails_when_the_served_dump_moves_mid_download(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """A dump swapped during the download is deleted, not kept as old."""
    dates = iter([_SERVED_DUMP_DATE, "2026-06-08"])
    monkeypatch.setattr(
        "etymyriad.__main__.served_dump_date", lambda _client: next(dates)
    )

    assert main(["fetch-dump"]) == 1

    assert "2026-06-08" in caplog.text
    assert not datafiles.raw_dump_path(_SERVED_DUMP_DATE).exists()


def test_all_downloads_and_filters_when_nothing_is_local(
    downloads: list[Path],
    data_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """With an empty data directory, `all` fetches the dump and uses it."""
    calls = _stub_load_edges(monkeypatch)
    _set_env(monkeypatch)

    assert main(["all"]) == 0

    assert downloads == [datafiles.raw_dump_path(_SERVED_DUMP_DATE)]
    dump = data_dir / "etymyriad-data.jsonl"
    assert json.loads(dump.read_text(encoding="utf-8"))["word"] == "aqua"
    assert calls


def test_all_downloads_when_the_served_dump_is_newer(
    downloads: list[Path],
    data_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A page date past the local dump's date fetches and re-filters."""
    _stub_load_edges(monkeypatch)
    dump = _filtered_dump(data_dir, field_paths(), raw_date="2026-05-01")
    _age(dump, 1_000)
    _set_env(monkeypatch)

    assert main(["all"]) == 0

    assert downloads == [datafiles.raw_dump_path(_SERVED_DUMP_DATE)]
    assert json.loads(dump.read_text(encoding="utf-8"))["word"] == "aqua"


def test_all_skips_the_download_when_the_local_dump_is_current(
    downloads: list[Path],
    data_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A local dump dated like the page is reused as it is."""
    _stub_load_edges(monkeypatch)
    dump = _filtered_dump(data_dir, field_paths())
    _set_env(monkeypatch)

    assert main(["all"]) == 0

    assert downloads == []
    assert "frijaz" in dump.read_text(encoding="utf-8")


def test_all_refilters_a_filtered_dump_older_than_the_raw_dump(
    downloads: list[Path],
    data_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A run cut off after the download resumes at the filter step."""
    _stub_load_edges(monkeypatch)
    dump = _filtered_dump(data_dir, field_paths())
    raw = datafiles.raw_dump_path(_SERVED_DUMP_DATE)
    raw.write_bytes(gzip.compress(_AQUA_ENTRY.encode()))
    _age(dump, 1_000)
    _age(raw, 2_000)
    _set_env(monkeypatch)

    assert main(["all"]) == 0

    assert downloads == []
    assert json.loads(dump.read_text(encoding="utf-8"))["word"] == "aqua"


def test_all_reuses_an_existing_edge_file(
    tmp_path: Path, data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`all` reuses an existing edge file instead of re-parsing."""
    calls = _stub_load_edges(monkeypatch)
    _filtered_dump(
        data_dir, field_paths(), "irrelevant: normalize must not run\n"
    )
    edges = tmp_path / "edges.jsonl"
    write_edges(edges, [_INHERITED_EDGE])

    def _boom(*_args: object, **_kwargs: object) -> object:
        msg = "normalize must not run when the edge file exists"
        raise AssertionError(msg)

    monkeypatch.setattr("etymyriad.__main__.normalize", _boom)
    _set_env(monkeypatch)

    assert main(["all", "--edges", str(edges)]) == 0

    assert calls[0][0] == [_INHERITED_EDGE]


def test_all_force_normalize_rebuilds_an_existing_edge_file(
    tmp_path: Path, data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """--force-normalize re-parses the dump even over an existing edge file."""
    calls = _stub_load_edges(monkeypatch)
    _filtered_dump(data_dir, field_paths())
    edges = tmp_path / "edges.jsonl"
    write_edges(edges, [])
    _set_env(monkeypatch)

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
    monkeypatch.setattr("etymyriad.__main__.sync_snapshot", _fake_sync)

    code = main(["sync-languages", "--output", str(tmp_path / "r.json")])

    assert code == 0
    assert written == [tmp_path / "r.json"]


def test_crosscheck_reports_tree_edges_the_graph_lacks(
    data_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Each tree edge absent from the edge file is listed and counted."""
    _filtered_dump(
        data_dir,
        field_paths(),
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
    _set_env(monkeypatch)

    exit_code = main(["crosscheck", "--edges", str(edges), "--limit", "5"])

    assert exit_code == 0
    out = capsys.readouterr().out
    assert "wine (en): ang:wīn -> enm:wyn (inherited)" in out
    assert "checked 1 trees: 2 edges, 1 missing" in out


def test_crosscheck_fetches_trees_as_of_the_local_dump_date(
    data_dir: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The raw dump's date reaches every tree fetch."""
    _filtered_dump(
        data_dir,
        field_paths(),
        json.dumps({
            "word": "wine",
            "lang_code": "en",
            "etymology_templates": [
                {"name": "etymon", "args": {"2": ":inh", "tree": "1"}}
            ],
        })
        + "\n",
    )
    edges = tmp_path / "edges.jsonl"
    write_edges(edges, [])
    dates: list[str] = []

    def _fake_fetch(
        _client: object, _headword: str, _lang: str, dump_date: str
    ) -> None:
        dates.append(dump_date)

    monkeypatch.setattr("etymyriad.__main__.fetch_tree", _fake_fetch)
    monkeypatch.setattr("etymyriad.__main__.served_dump_date", _no_dump_date)
    datafiles.raw_dump_path("2026-09-02").write_bytes(b"")
    _set_env(monkeypatch)

    main(["crosscheck", "--edges", str(edges)])

    assert dates == ["2026-09-02"]


def _age(path: Path, seconds: int) -> Path:
    """Pin a file's modification time.

    Returns:
        The same path.
    """
    os.utime(path, (seconds, seconds))
    return path


def test_normalize_writes_the_default_edge_file(
    data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """With no --edges, `normalize` writes data/etymyriad-edges.jsonl."""
    _filtered_dump(data_dir, field_paths())
    _set_env(monkeypatch)

    assert main(["normalize"]) == 0

    assert (data_dir / "etymyriad-edges.jsonl").read_text().strip()


def test_normalize_replaces_the_previous_edge_file(
    data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A rerun overwrites the edge file; no second one appears."""
    dump = _filtered_dump(data_dir, field_paths())
    edges = data_dir / "etymyriad-edges.jsonl"
    write_edges(edges, [_INHERITED_EDGE])
    _set_env(monkeypatch)

    assert main(["normalize"]) == 0

    assert sorted(path.name for path in data_dir.iterdir()) == [
        "etymyriad-data.fields.json",
        dump.name,
        edges.name,
        datafiles.raw_dump_path(_SERVED_DUMP_DATE).name,
    ]
    assert "aqua" not in edges.read_text(encoding="utf-8")


def test_all_reuses_a_current_default_edge_file(
    data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An edge file written after its dump is loaded without re-parsing."""
    calls = _stub_load_edges(monkeypatch)
    dump = _filtered_dump(
        data_dir, field_paths(), "irrelevant: normalize must not run\n"
    )
    _age(dump, 1_000)
    edges = data_dir / "etymyriad-edges.jsonl"
    write_edges(edges, [_INHERITED_EDGE])
    _age(edges, 2_000)

    def _boom(*_args: object, **_kwargs: object) -> object:
        msg = "normalize must not run when the edge file is current"
        raise AssertionError(msg)

    monkeypatch.setattr("etymyriad.__main__.normalize", _boom)
    _set_env(monkeypatch)

    assert main(["all"]) == 0

    assert calls[0][0] == [_INHERITED_EDGE]


def test_all_renormalizes_an_edge_file_older_than_its_dump(
    data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A dump rewritten after its edge file makes the edge file stale."""
    calls = _stub_load_edges(monkeypatch)
    dump = _filtered_dump(data_dir, field_paths())
    _age(dump, 2_000)
    edges = data_dir / "etymyriad-edges.jsonl"
    write_edges(edges, [_INHERITED_EDGE])
    _age(edges, 1_000)
    _set_env(monkeypatch)

    assert main(["all"]) == 0

    assert calls[0][0]
    assert _INHERITED_EDGE not in calls[0][0]


def test_load_defaults_to_the_current_edge_file(
    data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`load` reads the default edge file when it postdates the dump."""
    calls = _stub_load_edges(monkeypatch)
    _age(_filtered_dump(data_dir, field_paths()), 1_000)
    edges = data_dir / "etymyriad-edges.jsonl"
    write_edges(edges, [_INHERITED_EDGE])
    _age(edges, 2_000)
    _set_env(monkeypatch)

    assert main(["load"]) == 0

    assert calls[0][0] == [_INHERITED_EDGE]


def test_load_refuses_an_edge_file_older_than_its_dump(
    data_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A dump not yet normalized sends the user to normalize first."""
    _stub_load_edges(monkeypatch)
    _age(_filtered_dump(data_dir, field_paths()), 2_000)
    edges = data_dir / "etymyriad-edges.jsonl"
    write_edges(edges, [])
    _age(edges, 1_000)
    _set_env(monkeypatch)

    assert main(["load"]) == 2

    assert "etymyriad normalize" in capsys.readouterr().err


def test_load_refuses_edges_older_than_the_raw_dump(
    data_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A fetched dump newer than the edge file stops `load`."""
    calls = _stub_load_edges(monkeypatch)
    dump = _filtered_dump(data_dir, field_paths())
    edges = data_dir / "etymyriad-edges.jsonl"
    write_edges(edges, [_INHERITED_EDGE])
    raw = datafiles.raw_dump_path("2026-09-02")
    raw.write_bytes(b"")
    _age(dump, 500)
    _age(edges, 1_000)
    _age(raw, 2_000)
    _set_env(monkeypatch)

    assert main(["load"]) == 2

    assert calls == []
    assert "etymyriad normalize" in capsys.readouterr().err


@pytest.mark.usefixtures("local_raw_dump")
def test_load_without_a_dump_reads_the_edge_file(
    data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """With no dump to match, `load` reads whatever edge file exists."""
    calls = _stub_load_edges(monkeypatch)
    write_edges(data_dir / "etymyriad-edges.jsonl", [_INHERITED_EDGE])
    _set_env(monkeypatch)

    assert main(["load"]) == 0

    assert calls[0][0] == [_INHERITED_EDGE]


@pytest.mark.parametrize("command", ["load", "crosscheck"])
def test_edge_readers_exit_2_without_an_edge_file(
    data_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    command: str,
) -> None:
    """With no --edges and no edge file, the command says how to fix it."""
    _filtered_dump(data_dir, field_paths())
    _set_env(monkeypatch)

    assert main([command]) == 2

    assert "etymyriad normalize" in capsys.readouterr().err


def test_all_normalizes_into_the_default_edge_file(
    data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`all` with no edge file normalizes the dump into the default one."""
    calls = _stub_load_edges(monkeypatch)
    _filtered_dump(data_dir, field_paths())
    _set_env(monkeypatch)

    assert main(["all"]) == 0

    assert (data_dir / "etymyriad-edges.jsonl").is_file()
    assert calls[0][0]


def _filtered_dump(
    data_dir: Path,
    fields: Iterable[str] | None,
    entries: str = _FRIJAZ_ENTRY,
    raw_date: str = _SERVED_DUMP_DATE,
) -> Path:
    """Write the filtered dump, with a sidecar unless fields is None.

    Also writes the raw dump it supposedly came from, older than it.

    Args:
        data_dir: The redirected data directory, created if missing.
        fields: The field paths the sidecar lists, or None for no sidecar.
        entries: The dump's JSONL text.
        raw_date: The date the raw dump on disk carries.

    Returns:
        The dump's path.
    """
    data_dir.mkdir(exist_ok=True)
    dump = data_dir / "etymyriad-data.jsonl"
    dump.write_text(entries, encoding="utf-8")
    if fields is not None:
        datafiles.write_fields(dump, fields)
    raw = datafiles.raw_dump_path(raw_date)
    raw.write_bytes(b"")
    _age(raw, 0)
    return dump


def test_normalize_refuses_a_filtered_dump_without_a_sidecar(
    data_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A trimmed dump whose kept fields are unknown is not read."""
    _filtered_dump(data_dir, None)
    _set_env(monkeypatch)

    assert main(["normalize"]) == 2

    assert "re-run `etymyriad filter`" in capsys.readouterr().err


def test_normalize_refuses_a_dump_missing_a_parsed_field(
    data_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A dump filtered before the parser read a field names that field."""
    kept = field_paths() - {"senses.form_of.word"}
    _filtered_dump(data_dir, kept)
    _set_env(monkeypatch)

    assert main(["normalize"]) == 2

    assert "senses.form_of.word" in capsys.readouterr().err


def test_normalize_accepts_a_sidecar_with_retired_fields(
    data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Fields the models no longer declare cost bytes, not edges."""
    kept = field_paths() | {"retired_field"}
    _filtered_dump(data_dir, kept)
    _set_env(monkeypatch)

    assert main(["normalize"]) == 0


def test_filter_refuses_a_trimmed_input_missing_parsed_fields(
    tmp_path: Path,
    data_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Re-trimming an old filtered file can't vouch for fields it lacks."""
    kept = field_paths() - {"senses.form_of.word"}
    old = tmp_path / "old.jsonl"
    old.write_text(_FRIJAZ_ENTRY, encoding="utf-8")
    datafiles.write_fields(old, kept)
    _set_env(monkeypatch)

    assert main(["filter", "--input", str(old)]) == 2

    assert "senses.form_of.word" in capsys.readouterr().err
    assert not data_dir.exists()


def test_filter_refuses_a_sidecarless_dump_named_relatively(
    data_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A relative --input can't dodge the default dump's sidecar check."""
    _filtered_dump(data_dir, None)
    monkeypatch.chdir(data_dir)
    _set_env(monkeypatch)

    assert main(["filter", "--input", "etymyriad-data.jsonl"]) == 2

    assert "re-run `etymyriad filter`" in capsys.readouterr().err


def test_filter_reports_a_missing_input(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """An input that doesn't exist reports not found, not a sidecar."""
    _set_env(monkeypatch)

    with caplog.at_level(logging.ERROR):
        code = main(["filter", "--input", str(tmp_path / "gone.jsonl")])

    assert code == 1
    assert "not found" in caplog.text
