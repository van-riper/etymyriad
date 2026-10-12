"""Command-line entry point for `etymyriad`; `--help` lists commands."""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from collections import Counter
from itertools import islice
from pathlib import Path
from typing import TYPE_CHECKING

import httpx

from etymyriad.config import Config, redact_dsn, redact_secrets
from etymyriad.crosscheck import (
    fetch_tree,
    graph_index,
    missing_edges,
    tree_edges,
    tree_headwords,
)
from etymyriad.edgefile import read_edges, write_edges
from etymyriad.languages import (
    SNAPSHOT_PATH,
    USER_AGENT,
    filter_in_scope,
    sync_snapshot,
)
from etymyriad.load import load_edges
from etymyriad.model import EtymEdge
from etymyriad.normalize import normalize
from etymyriad.parse import stream_entries

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator, Mapping

    from etymyriad.model import GraphItem, RelType


_DEFAULT_EDGES = "data/edges.jsonl"
_DEFAULT_INE_OUTPUT = "data/raw/indo-european.jsonl"
_SYNC_TIMEOUT_SECONDS = 120
_FETCH_DELAY_SECONDS = 1
_DEFAULT_CROSSCHECK_LIMIT = 25
_log = logging.getLogger(__name__)


def _write_entries(path: str, entries: Iterable[Mapping[str, object]]) -> int:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with out.open("w", encoding="utf-8") as handle:
        for entry in entries:
            handle.write(json.dumps(entry, ensure_ascii=False))
            handle.write("\n")
            count += 1
    return count


def _fmt(count: int) -> str:
    """Format a count with thousands separators for CLI/log output.

    Returns:
        `count` formatted with thousands separators, e.g. "10,287,531".
    """
    return f"{count:,}"


def _tally_rel_types(
    edges: Iterable[GraphItem], counts: Counter[RelType]
) -> Iterator[GraphItem]:
    for item in edges:
        if isinstance(item, EtymEdge):
            counts[item.rel_type] += 1
        yield item


def _print_rel_type_breakdown(counts: Counter[RelType]) -> None:
    for rel_type, count in counts.most_common():
        print(f"  {rel_type}: {_fmt(count)}")


def _edges_file_is_fresh(edges_path: str, dump_path: str) -> bool:
    """Check whether an edge file already reflects the current dump.

    A heuristic, not a guarantee: it catches a changed dump but not a
    changed normalizer, which is what `--force-normalize` is for.

    Returns:
        True if `edges_path` exists and is at least as new as `dump_path`.
    """
    edges = Path(edges_path)
    if not edges.is_file():
        return False
    return edges.stat().st_mtime >= Path(dump_path).stat().st_mtime


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="etymyriad")
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Log at DEBUG level instead of INFO.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("parse", help="Inspect the dump: count entries.")
    filter_ine = subparsers.add_parser(
        "filter-ine",
        help="Narrow a combined Wiktextract dump to Indo-European entries.",
    )
    filter_ine.add_argument(
        "--input", required=True, help="Combined dump path (.jsonl or .gz)."
    )
    filter_ine.add_argument(
        "--output",
        default=_DEFAULT_INE_OUTPUT,
        help=f"Filtered JSONL output path (default: {_DEFAULT_INE_OUTPUT}).",
    )
    sync_languages = subparsers.add_parser(
        "sync-languages",
        help="Refresh the language registry snapshot from Wiktionary.",
    )
    sync_languages.add_argument(
        "--output",
        default=str(SNAPSHOT_PATH),
        help=f"Snapshot output path (default: {SNAPSHOT_PATH}).",
    )
    for name, verb in (("normalize", "output"), ("load", "input")):
        step = subparsers.add_parser(
            name,
            help=(
                "Parse and normalize the dump into an edge file."
                if name == "normalize"
                else "Load an edge file into Postgres."
            ),
        )
        step.add_argument(
            "--edges",
            default=_DEFAULT_EDGES,
            help=f"Edge JSONL {verb} path (default: {_DEFAULT_EDGES}).",
        )
    crosscheck = subparsers.add_parser(
        "crosscheck",
        help="Diff the edge file against Wiktionary's etymology trees.",
    )
    crosscheck.add_argument(
        "--edges",
        default=_DEFAULT_EDGES,
        help=f"Edge JSONL input path (default: {_DEFAULT_EDGES}).",
    )
    crosscheck.add_argument(
        "--limit",
        type=int,
        default=_DEFAULT_CROSSCHECK_LIMIT,
        help=(
            "Trees to fetch, one request per second "
            f"(default: {_DEFAULT_CROSSCHECK_LIMIT})."
        ),
    )
    all_parser = subparsers.add_parser(
        "all", help="Parse, normalize, and load in one pass."
    )
    all_parser.add_argument(
        "--edges",
        default=_DEFAULT_EDGES,
        help=(
            "Edge JSONL intermediate path, reused across runs when fresh "
            f"(default: {_DEFAULT_EDGES})."
        ),
    )
    for loading_parser in (subparsers.choices["load"], all_parser):
        loading_parser.add_argument(
            "--skip-sanity-gate",
            action="store_true",
            help="Swap even if term/edge counts moved more than 10%%.",
        )
    all_parser.add_argument(
        "--force-normalize",
        action="store_true",
        help="Re-parse the dump even if --edges looks up to date.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the ETL.

    Args:
        argv: Command-line arguments, or None to read from the process args.

    Returns:
        A process exit code (0 on success).
    """
    args = _build_parser().parse_args(argv)
    level = logging.DEBUG if args.debug else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    try:
        config = Config.from_env()
    except ValueError as e:
        print(e, file=sys.stderr)
        return 2
    needs_dump_date = {"load", "all", "crosscheck"}
    if args.command in needs_dump_date and config.dump_date is None:
        print(
            "set WIKTEXTRACT_DUMP_DATE to the dump's date (YYYY-MM-DD)",
            file=sys.stderr,
        )
        return 2

    try:
        if args.command == "crosscheck":
            return _crosscheck(args, config)
        return _dispatch(args, config)
    except Exception as e:  # ruff: ignore[blind-except] - last-resort DSN-safe guard
        _log.error("fatal: %s", redact_secrets(config.database_url, str(e)))
        return 1


def _require_dump_date(config: Config) -> str:
    if config.dump_date is None:
        msg = "WIKTEXTRACT_DUMP_DATE is unset"
        raise ValueError(msg)
    return config.dump_date


def _crosscheck(args: argparse.Namespace, config: Config) -> int:
    dump_date = _require_dump_date(config)
    index = graph_index(read_edges(args.edges))
    headwords = islice(
        tree_headwords(stream_entries(config.dump_path)), args.limit
    )
    checked = edge_count = missing_count = 0
    with httpx.Client(timeout=_SYNC_TIMEOUT_SECONDS) as client:
        for position, (headword, lang_code) in enumerate(headwords):
            if position:
                time.sleep(_FETCH_DELAY_SECONDS)
            tree = fetch_tree(client, headword, lang_code, dump_date)
            if tree is None:
                continue
            edges = tree_edges(tree)
            missing = missing_edges(edges, index)
            for edge in missing:
                print(
                    f"{headword} ({lang_code}): "
                    f"{edge.src_lang}:{edge.src_term} -> "
                    f"{edge.dst_lang}:{edge.dst_term} ({edge.keyword})"
                )
            checked += 1
            edge_count += len(edges)
            missing_count += len(missing)
    print(
        f"checked {_fmt(checked)} trees: {_fmt(edge_count)} edges, "
        f"{_fmt(missing_count)} missing"
    )
    return 0


def _dispatch(args: argparse.Namespace, config: Config) -> int:
    if args.command == "parse":
        count = sum(1 for _ in stream_entries(config.dump_path))
        print(f"parsed {_fmt(count)} entries")
        return 0

    if args.command == "filter-ine":
        entries = filter_in_scope(stream_entries(args.input))
        written = _write_entries(args.output, entries)
        print(
            f"filtered {_fmt(written)} Indo-European entries -> {args.output}"
        )
        return 0

    if args.command == "sync-languages":
        with httpx.Client(
            headers={"User-Agent": USER_AGENT},
            timeout=_SYNC_TIMEOUT_SECONDS,
        ) as client:
            snapshot = sync_snapshot(Path(args.output), client)
        print(
            f"synced {_fmt(len(snapshot['languages']))} languages, "
            f"{_fmt(len(snapshot['families']))} families, "
            f"{_fmt(len(snapshot['varieties']))} varieties -> {args.output}"
        )
        return 0

    if args.command == "normalize":
        counts: Counter[RelType] = Counter()
        edges = normalize(stream_entries(config.dump_path))
        written = write_edges(args.edges, _tally_rel_types(edges, counts))
        print(f"normalized {_fmt(written)} edges -> {args.edges}")
        _print_rel_type_breakdown(counts)
        return 0

    if args.command == "load":
        _log.info("loading into %s", redact_dsn(config.database_url))
        counts = Counter()
        loaded = load_edges(
            config.database_url,
            _tally_rel_types(read_edges(args.edges), counts),
            dump_date=_require_dump_date(config),
            check_drift=not args.skip_sanity_gate,
        )
        print(f"loaded {_fmt(loaded)} edges")
        _print_rel_type_breakdown(counts)
        return 0

    counts = Counter()
    if not args.force_normalize and _edges_file_is_fresh(
        args.edges, config.dump_path
    ):
        _log.info("reusing fresh edge file %s (skip normalize)", args.edges)
    else:
        _log.info("normalizing dump -> %s", args.edges)
        normalized = normalize(stream_entries(config.dump_path))
        written = write_edges(args.edges, normalized)
        _log.info("normalized %s edges -> %s", _fmt(written), args.edges)
    _log.info("loading into %s", redact_dsn(config.database_url))
    loaded = load_edges(
        config.database_url,
        _tally_rel_types(read_edges(args.edges), counts),
        dump_date=_require_dump_date(config),
        check_drift=not args.skip_sanity_gate,
    )
    print(f"loaded {_fmt(loaded)} edges")
    _print_rel_type_breakdown(counts)
    return 0


if __name__ == "__main__":
    sys.exit(main())  # pragma: no cover
