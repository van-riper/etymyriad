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

from etymyriad import datafiles
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
from etymyriad.normalize import field_paths, normalize, project_entry
from etymyriad.parse import stream_entries

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator, Mapping

    from etymyriad.model import GraphItem, RelType


_SYNC_TIMEOUT_SECONDS = 120
_FETCH_DELAY_SECONDS = 1
_DEFAULT_CROSSCHECK_LIMIT = 25
_log = logging.getLogger(__name__)


def _write_entries(path: Path, entries: Iterable[Mapping[str, object]]) -> int:
    count = 0
    with path.open("w", encoding="utf-8") as handle:
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


def _default_edges(command: str, config: Config) -> str | None:
    """Pick the edge file a command uses when --edges is omitted.

    Every command uses the edge file of its dump: stamped like the dump,
    or by the dump's modification time for an unstamped dump, so `all`
    reuses it while the dump is unchanged. `load` and `crosscheck` read
    that file only if it exists, so a load never pairs one dump's edges
    with another's date. With no dump at all, `load` reads the newest
    edge file.

    Returns:
        The path, or None when there is no edge file to read.
    """
    if config.dump_path is None:
        latest = datafiles.latest_file(
            datafiles.DATA_DIR, datafiles.EDGES_PREFIX
        )
        return None if latest is None else str(latest)
    stamp = (
        datafiles.stamp_of(config.dump_path)
        or datafiles.modified_stamp(config.dump_path)
        # A missing dump fails in stream_entries; any name will do.
        or datafiles.new_stamp()
    )
    edges = datafiles.edges_path(stamp)
    if command in {"normalize", "all"} or edges.is_file():
        return str(edges)
    return None


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="etymyriad")
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Log at DEBUG level instead of INFO.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("parse", help="Inspect the dump: count entries.")
    filter_parser = subparsers.add_parser(
        "filter",
        help="Narrow a combined dump to the languages and fields in scope.",
    )
    filter_parser.add_argument(
        "--input", required=True, help="Combined dump path (.jsonl or .gz)."
    )
    filter_parser.add_argument(
        "--output",
        help="Filtered JSONL path (default: a new stamped file in data/).",
    )
    subparsers.add_parser(
        "prune",
        help="Delete stamped files older than the newest filtered dump.",
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
    normalize_parser = subparsers.add_parser(
        "normalize", help="Parse and normalize the dump into an edge file."
    )
    normalize_parser.add_argument(
        "--edges",
        help=(
            "Edge JSONL output path "
            "(default: data/etymyriad-edges-<dump stamp>.jsonl)."
        ),
    )
    load_parser = subparsers.add_parser(
        "load", help="Load an edge file into Postgres."
    )
    crosscheck = subparsers.add_parser(
        "crosscheck",
        help="Diff the edge file against Wiktionary's etymology trees.",
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
        help=(
            "Edge JSONL path, reused if it exists "
            "(default: data/etymyriad-edges-<dump stamp>.jsonl)."
        ),
    )
    for edge_reader in (load_parser, crosscheck):
        edge_reader.add_argument(
            "--edges",
            help=(
                "Edge JSONL input path "
                "(default: the dump's data/etymyriad-edges-<stamp>.jsonl)."
            ),
        )
    for loading_parser in (load_parser, all_parser):
        loading_parser.add_argument(
            "--skip-sanity-gate",
            action="store_true",
            help="Swap even if term/edge counts moved more than 10%%.",
        )
    all_parser.add_argument(
        "--force-normalize",
        action="store_true",
        help="Re-parse the dump even if the edge file exists.",
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
    usage_error = _resolve_usage(args, config)
    if usage_error is not None:
        print(usage_error, file=sys.stderr)
        return 2

    try:
        if args.command == "crosscheck":
            return _crosscheck(args, config)
        if args.command == "prune":
            return _prune(config)
        return _dispatch(args, config)
    except Exception as e:  # ruff: ignore[blind-except] - last-resort DSN-safe guard
        _log.error("fatal: %s", redact_secrets(config.database_url, str(e)))
        return 1


def _resolve_usage(args: argparse.Namespace, config: Config) -> str | None:
    """Check a command has what it reads, filling in a default --edges.

    Returns:
        A message saying what is missing and how to supply it, or None
        when the command can run.
    """
    needs_dump_date = {"load", "all", "crosscheck"}
    if args.command in needs_dump_date and config.dump_date is None:
        return "set WIKTEXTRACT_DUMP_DATE to the dump's date (YYYY-MM-DD)"
    needs_dump = {"parse", "normalize", "all", "crosscheck"}
    if args.command in needs_dump and config.dump_path is None:
        return (
            "no filtered dump in data/: run `etymyriad filter`, "
            "or set WIKTEXTRACT_DUMP"
        )
    if args.command in {"normalize", "all", "crosscheck"}:
        fields_error = _missing_fields_error(_require_dump_path(config))
        if fields_error is not None:
            return fields_error
    reads_edges = {"normalize", "load", "all", "crosscheck"}
    if args.command in reads_edges and args.edges is None:
        args.edges = _default_edges(args.command, config)
        if args.edges is None:
            return (
                "no edge file in data/: run `etymyriad normalize`, "
                "or pass --edges"
            )
    return None


def _missing_fields_error(dump_path: str) -> str | None:
    """Explain why a dump lacks fields the parser reads, if it does.

    A dump with a sidecar, or a stamped name, was trimmed by `filter`.
    Any other dump, such as the raw `.gz`, carries every field. A dump
    that doesn't exist is left for `stream_entries` to report.

    Returns:
        An error message, or None when the dump is safe to read.
    """
    dump = Path(dump_path)
    if not dump.exists():
        return None
    kept = datafiles.read_fields(dump)
    if kept is None:
        if datafiles.stamp_of(dump) is None:
            return None
        sidecar = datafiles.fields_path(dump).name
        return f"{dump} has no {sidecar}: re-run `etymyriad filter`"
    missing = ", ".join(sorted(field_paths() - kept))
    if not missing:
        return None
    return (
        f"{dump} lacks fields the parser reads ({missing}): "
        "re-run `etymyriad filter`"
    )


def _require_dump_date(config: Config) -> str:
    if config.dump_date is None:
        msg = "WIKTEXTRACT_DUMP_DATE is unset"
        raise ValueError(msg)
    return config.dump_date


def _require_dump_path(config: Config) -> str:
    if config.dump_path is None:
        msg = "no dump to read"
        raise ValueError(msg)
    return config.dump_path


def _crosscheck(args: argparse.Namespace, config: Config) -> int:
    dump_date = _require_dump_date(config)
    index = graph_index(read_edges(args.edges))
    headwords = islice(
        tree_headwords(stream_entries(_require_dump_path(config))), args.limit
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


def _prune(config: Config) -> int:
    keep = (
        None
        if config.dump_path is None
        else datafiles.stamp_of(config.dump_path)
    )
    stale = datafiles.stale_files(datafiles.DATA_DIR, keep)
    if not stale:
        print("nothing to prune")
        return 0
    freed_bytes = 0
    for path in stale:
        freed_bytes += path.stat().st_size
        path.unlink()
        print(f"deleted {path.name}")
    print(f"freed {freed_bytes / 1e9:.1f} GB")
    return 0


def _dispatch(args: argparse.Namespace, config: Config) -> int:
    if args.command == "parse":
        count = sum(1 for _ in stream_entries(_require_dump_path(config)))
        print(f"parsed {_fmt(count)} entries")
        return 0

    if args.command == "filter":
        output = (
            Path(args.output)
            if args.output
            else datafiles.data_path(datafiles.new_stamp())
        )
        entries = map(
            project_entry, filter_in_scope(stream_entries(args.input))
        )
        with datafiles.staged_path(output) as staged:
            written = _write_entries(staged, entries)
            datafiles.write_fields(output, field_paths())
        print(f"filtered {_fmt(written)} entries -> {output}")
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
        edges = normalize(stream_entries(_require_dump_path(config)))
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
    if not args.force_normalize and Path(args.edges).is_file():
        _log.info("reusing edge file %s (skip normalize)", args.edges)
    else:
        _log.info("normalizing dump -> %s", args.edges)
        normalized = normalize(stream_entries(_require_dump_path(config)))
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
