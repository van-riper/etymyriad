"""Tests for the command-line entry point."""

from __future__ import annotations

import io
import json
import logging
import os
from collections import Counter
from typing import TYPE_CHECKING

import psycopg

from etymyriad.__main__ import _fmt, _print_rel_type_breakdown, main
from etymyriad.edgefile import write_edges
from etymyriad.model import EtymEdge, Lexeme, RelType

if TYPE_CHECKING:
    from pathlib import Path

    import pytest


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
        '{"word": "etymology", "lang": "English"}\n'
        '{"word": "水", "lang": "Japanese"}\n'
        '{"word": "aqua", "lang": "Latin"}\n',
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


def test_load_inserts_edges_from_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    db_url: str,
) -> None:
    """The load subcommand reads an edge file and inserts it into Postgres."""
    edge = EtymEdge(
        src=Lexeme(lang_code="la", headword="aqua", source_ref="w:a"),
        dst=Lexeme(lang_code="es", headword="agua", source_ref="w:b"),
        rel_type=RelType.INHERITED,
        source_ref="w:e",
    )
    edges = tmp_path / "edges.jsonl"
    write_edges(edges, [edge])
    monkeypatch.setenv("DATABASE_URL", db_url)
    monkeypatch.setenv("WIKTEXTRACT_DUMP", "/does/not/matter.jsonl")
    monkeypatch.setenv("WIKTEXTRACT_DUMP_DATE", "2026-06-01")

    code = main(["load", "--edges", str(edges)])

    assert code == 0
    with psycopg.connect(db_url) as conn:
        edge_count = conn.execute("SELECT count(*) FROM etymology").fetchone()
    assert edge_count is not None
    assert edge_count[0] == 1


def test_load_prints_rel_type_breakdown(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    db_url: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The load subcommand reports edge counts broken down by rel_type."""
    edges_data = [
        EtymEdge(
            src=Lexeme(lang_code="la", headword="aqua", source_ref="w:a"),
            dst=Lexeme(lang_code="es", headword="agua", source_ref="w:b"),
            rel_type=RelType.INHERITED,
            source_ref="w:e",
        ),
        EtymEdge(
            src=Lexeme(lang_code="la", headword="aqua", source_ref="w:a"),
            dst=Lexeme(lang_code="fr", headword="eau", source_ref="w:c"),
            rel_type=RelType.INHERITED,
            source_ref="w:f",
        ),
        EtymEdge(
            src=Lexeme(lang_code="en", headword="water", source_ref="w:g"),
            dst=Lexeme(lang_code="de", headword="Wasser", source_ref="w:h"),
            rel_type=RelType.COGNATE,
            source_ref="w:i",
        ),
    ]
    edges = tmp_path / "edges.jsonl"
    write_edges(edges, edges_data)
    monkeypatch.setenv("DATABASE_URL", db_url)
    monkeypatch.setenv("WIKTEXTRACT_DUMP", "/does/not/matter.jsonl")
    monkeypatch.setenv("WIKTEXTRACT_DUMP_DATE", "2026-06-01")

    code = main(["load", "--edges", str(edges)])

    assert code == 0
    out = capsys.readouterr().out
    assert "inherited: 2" in out
    assert "cognate: 1" in out


def _run_load_capturing_loader_logs(
    argv: list[str], edges: Path, monkeypatch: pytest.MonkeyPatch, db_url: str
) -> tuple[int, str]:
    """Run `main` with logging configured for real, capturing the loader.

    pytest's own capture handler sits on the root logger, which makes
    `logging.basicConfig` a no-op; clearing root's handlers for the call
    lets the CLI set the level for real, and a handler on the loader's
    own logger collects whatever that level lets through.

    Args:
        argv: Arguments to pass to `main`.
        edges: Edge file path to write a single loadable edge to.
        monkeypatch: Fixture used to point the CLI at `db_url`.
        db_url: DSN for the test database.

    Returns:
        `main`'s exit code and everything the loader logged.
    """
    write_edges(
        edges,
        [
            EtymEdge(
                src=Lexeme(lang_code="la", headword="aqua", source_ref="w:a"),
                dst=Lexeme(lang_code="es", headword="agua", source_ref="w:b"),
                rel_type=RelType.INHERITED,
                source_ref="w:e",
            )
        ],
    )
    monkeypatch.setenv("DATABASE_URL", db_url)
    monkeypatch.setenv("WIKTEXTRACT_DUMP", "/does/not/matter.jsonl")
    monkeypatch.setenv("WIKTEXTRACT_DUMP_DATE", "2026-06-01")

    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    loader_log = logging.getLogger("etymyriad.load")
    root = logging.getLogger()
    original_handlers = root.handlers[:]
    original_level = root.level
    root.handlers.clear()
    loader_log.addHandler(handler)
    try:
        code = main(argv)
    finally:
        loader_log.removeHandler(handler)
        root.handlers[:] = original_handlers
        root.setLevel(original_level)
    return code, stream.getvalue()


def test_debug_flag_surfaces_the_loader_s_debug_lines(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    db_url: str,
) -> None:
    """--debug actually emits the loader's DEBUG lines, not just a level."""
    code, logs = _run_load_capturing_loader_logs(
        ["--debug", "load", "--edges", str(tmp_path / "edges.jsonl")],
        tmp_path / "edges.jsonl",
        monkeypatch,
        db_url,
    )

    assert code == 0
    assert "2 language(s)" in logs


def test_load_without_debug_omits_the_loader_s_debug_lines(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    db_url: str,
) -> None:
    """Without --debug the DEBUG lines stay silent, while INFO still flows."""
    code, logs = _run_load_capturing_loader_logs(
        ["load", "--edges", str(tmp_path / "edges.jsonl")],
        tmp_path / "edges.jsonl",
        monkeypatch,
        db_url,
    )

    assert code == 0
    assert "language(s)" not in logs
    assert "staged 1 items" in logs


def test_load_subcommand_computes_degree(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    db_url: str,
) -> None:
    """`load` computes each lexeme's degree from the loaded edges."""
    edge = EtymEdge(
        src=Lexeme(lang_code="la", headword="aqua", source_ref="w:a"),
        dst=Lexeme(lang_code="es", headword="agua", source_ref="w:b"),
        rel_type=RelType.INHERITED,
        source_ref="w:e",
    )
    edges = tmp_path / "edges.jsonl"
    write_edges(edges, [edge])
    monkeypatch.setenv("DATABASE_URL", db_url)
    monkeypatch.setenv("WIKTEXTRACT_DUMP", "/does/not/matter.jsonl")
    monkeypatch.setenv("WIKTEXTRACT_DUMP_DATE", "2026-06-01")

    code = main(["load", "--edges", str(edges)])

    assert code == 0
    with psycopg.connect(db_url) as conn:
        degrees = [row[0] for row in conn.execute("SELECT degree FROM lexeme")]
    # One edge touches both lexemes once each: degree 1 apiece.
    assert degrees == [1, 1]


def test_all_subcommand_also_computes_degree(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    db_url: str,
) -> None:
    """`all` wires parse -> normalize -> load, including degree."""
    dump = tmp_path / "dump.jsonl"
    dump.write_text(
        '{"word": "frijaz", "lang_code": "gem-pro", "pos": "adj", '
        '"senses": [{"glosses": ["free"]}], '
        '"etymology_templates": [{"name": "inh", "args": '
        '{"1": "gem-pro", "2": "ine-pro", "3": "*priH\\u00f3s"}}]}\n',
        encoding="utf-8",
    )
    edges = tmp_path / "edges.jsonl"
    monkeypatch.setenv("DATABASE_URL", db_url)
    monkeypatch.setenv("WIKTEXTRACT_DUMP", str(dump))
    monkeypatch.setenv("WIKTEXTRACT_DUMP_DATE", "2026-06-01")

    code = main(["all", "--edges", str(edges)])

    assert code == 0
    with psycopg.connect(db_url) as conn:
        lexeme_count = conn.execute("SELECT count(*) FROM lexeme").fetchone()
        degree_count = conn.execute(
            "SELECT count(*) FROM lexeme WHERE degree > 0"
        ).fetchone()
    assert lexeme_count is not None
    assert degree_count is not None
    assert lexeme_count[0] > 0
    assert degree_count[0] > 0


def test_all_writes_edges_file_instead_of_discarding_it(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    db_url: str,
) -> None:
    """`all` persists the normalized edges instead of discarding them."""
    dump = tmp_path / "dump.jsonl"
    dump.write_text(
        '{"word": "frijaz", "lang_code": "gem-pro", "pos": "adj", '
        '"senses": [{"glosses": ["free"]}], '
        '"etymology_templates": [{"name": "inh", "args": '
        '{"1": "gem-pro", "2": "ine-pro", "3": "*priH\\u00f3s"}}]}\n',
        encoding="utf-8",
    )
    edges = tmp_path / "edges.jsonl"
    monkeypatch.setenv("DATABASE_URL", db_url)
    monkeypatch.setenv("WIKTEXTRACT_DUMP", str(dump))
    monkeypatch.setenv("WIKTEXTRACT_DUMP_DATE", "2026-06-01")

    code = main(["all", "--edges", str(edges)])

    assert code == 0
    assert edges.exists()
    assert edges.read_text().strip()


def test_all_skips_normalize_when_edges_file_is_fresh(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    db_url: str,
) -> None:
    """`all` reuses a fresh edges.jsonl instead of re-parsing the dump."""
    dump = tmp_path / "dump.jsonl"
    dump.write_text("irrelevant: normalize must not run\n", encoding="utf-8")
    edge = EtymEdge(
        src=Lexeme(lang_code="la", headword="aqua", source_ref="w:a"),
        dst=Lexeme(lang_code="es", headword="agua", source_ref="w:b"),
        rel_type=RelType.INHERITED,
        source_ref="w:e",
    )
    edges = tmp_path / "edges.jsonl"
    write_edges(edges, [edge])
    os.utime(dump, (1_000, 1_000))
    os.utime(edges, (2_000, 2_000))

    def _boom(*_args: object, **_kwargs: object) -> object:
        msg = "normalize must not run when edges.jsonl is fresh"
        raise AssertionError(msg)

    monkeypatch.setattr("etymyriad.__main__.normalize", _boom)
    monkeypatch.setenv("DATABASE_URL", db_url)
    monkeypatch.setenv("WIKTEXTRACT_DUMP", str(dump))
    monkeypatch.setenv("WIKTEXTRACT_DUMP_DATE", "2026-06-01")

    code = main(["all", "--edges", str(edges)])

    assert code == 0
    with psycopg.connect(db_url) as conn:
        edge_count = conn.execute("SELECT count(*) FROM etymology").fetchone()
    assert edge_count is not None
    assert edge_count[0] == 1


def test_all_reparses_when_dump_is_newer_than_edges_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    db_url: str,
) -> None:
    """A dump touched after edges.jsonl was written forces a re-normalize."""
    dump = tmp_path / "dump.jsonl"
    dump.write_text(
        '{"word": "frijaz", "lang_code": "gem-pro", "pos": "adj", '
        '"senses": [{"glosses": ["free"]}], '
        '"etymology_templates": [{"name": "inh", "args": '
        '{"1": "gem-pro", "2": "ine-pro", "3": "*priH\\u00f3s"}}]}\n',
        encoding="utf-8",
    )
    edges = tmp_path / "edges.jsonl"
    write_edges(edges, [])
    os.utime(edges, (1_000, 1_000))
    os.utime(dump, (2_000, 2_000))
    monkeypatch.setenv("DATABASE_URL", db_url)
    monkeypatch.setenv("WIKTEXTRACT_DUMP", str(dump))
    monkeypatch.setenv("WIKTEXTRACT_DUMP_DATE", "2026-06-01")

    code = main(["all", "--edges", str(edges)])

    assert code == 0
    with psycopg.connect(db_url) as conn:
        lexeme_count = conn.execute("SELECT count(*) FROM lexeme").fetchone()
    assert lexeme_count is not None
    assert lexeme_count[0] > 0


def test_all_force_normalize_reruns_even_when_fresh(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    db_url: str,
) -> None:
    """--force-normalize re-parses the dump even over a fresh edges.jsonl."""
    dump = tmp_path / "dump.jsonl"
    dump.write_text(
        '{"word": "frijaz", "lang_code": "gem-pro", "pos": "adj", '
        '"senses": [{"glosses": ["free"]}], '
        '"etymology_templates": [{"name": "inh", "args": '
        '{"1": "gem-pro", "2": "ine-pro", "3": "*priH\\u00f3s"}}]}\n',
        encoding="utf-8",
    )
    edges = tmp_path / "edges.jsonl"
    write_edges(edges, [])
    os.utime(dump, (1_000, 1_000))
    os.utime(edges, (2_000, 2_000))
    monkeypatch.setenv("DATABASE_URL", db_url)
    monkeypatch.setenv("WIKTEXTRACT_DUMP", str(dump))
    monkeypatch.setenv("WIKTEXTRACT_DUMP_DATE", "2026-06-01")

    code = main(["all", "--edges", str(edges), "--force-normalize"])

    assert code == 0
    with psycopg.connect(db_url) as conn:
        lexeme_count = conn.execute("SELECT count(*) FROM lexeme").fetchone()
    assert lexeme_count is not None
    assert lexeme_count[0] > 0


def test_all_normalizes_when_edges_file_is_missing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    db_url: str,
) -> None:
    """With no prior edges.jsonl, `all` always normalizes."""
    dump = tmp_path / "dump.jsonl"
    dump.write_text(
        '{"word": "frijaz", "lang_code": "gem-pro", "pos": "adj", '
        '"senses": [{"glosses": ["free"]}], '
        '"etymology_templates": [{"name": "inh", "args": '
        '{"1": "gem-pro", "2": "ine-pro", "3": "*priH\\u00f3s"}}]}\n',
        encoding="utf-8",
    )
    edges = tmp_path / "edges.jsonl"
    monkeypatch.setenv("DATABASE_URL", db_url)
    monkeypatch.setenv("WIKTEXTRACT_DUMP", str(dump))
    monkeypatch.setenv("WIKTEXTRACT_DUMP_DATE", "2026-06-01")

    code = main(["all", "--edges", str(edges)])

    assert code == 0
    with psycopg.connect(db_url) as conn:
        lexeme_count = conn.execute("SELECT count(*) FROM lexeme").fetchone()
    assert lexeme_count is not None
    assert lexeme_count[0] > 0
