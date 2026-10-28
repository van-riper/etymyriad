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
from etymyriad.config import (
    CROSSCHECK_FETCH_DELAY_SECONDS,
    DEFAULT_CROSSCHECK_LIMIT,
    HTTP_TIMEOUT_SECONDS,
    USER_AGENT,
    Config,
    redact_dsn,
    redact_secrets,
)
from etymyriad.crosscheck import (
    fetch_tree,
    graph_index,
    missing_edges,
    tree_edges,
    tree_headwords,
)
from etymyriad.edgefile import read_edges, write_edges
from etymyriad.kaikki import download_raw_dump, served_dump_date
from etymyriad.languages import SNAPSHOT_PATH, filter_in_scope, sync_snapshot
from etymyriad.load import load_edges
from etymyriad.model import EtymEdge
from etymyriad.normalize import field_paths, normalize, project_entry
from etymyriad.parse import stream_entries

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator, Mapping

    from etymyriad.model import GraphItem, RelType


_REFILTER = "re-run `etymyriad filter` on the raw dump"
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


def _print_load_total(loaded: int, counts: Counter[RelType]) -> None:
    print(f"loaded {_fmt(loaded)} edges from {_fmt(counts.total())} staged")


def _print_rel_type_breakdown(counts: Counter[RelType]) -> None:
    for rel_type, count in counts.most_common():
        print(f"  {rel_type}: {_fmt(count)}")


def _default_edges(command: str, config: Config) -> str | None:
    """Pick the edge file a command uses when --edges is omitted.

    `normalize` and `all` use the default edge file whether or not it
    exists. `load` and `crosscheck` use it only when it exists and is no
    older than the filtered dump or the raw dump, so a load never pairs
    one dump's edges with another's date.

    Returns:
        The path, or None when there is no edge file to read.
    """
    edges = datafiles.edges_path()
    if command in {"normalize", "all"}:
        return str(edges)
    raw_date = datafiles.local_dump_date()
    if raw_date is not None and not datafiles.is_current(
        edges, datafiles.raw_dump_path(raw_date)
    ):
        return None
    if config.dump_path is None:
        return str(edges) if edges.is_file() else None
    if datafiles.is_current(edges, Path(config.dump_path)):
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
    subparsers.add_parser(
        "fetch-dump",
        help="Download the raw dump kaikki.org serves, unless it is local.",
    )
    filter_parser = subparsers.add_parser(
        "filter",
        help="Narrow a combined dump to the languages and fields in scope.",
    )
    filter_parser.add_argument(
        "--input", required=True, help="Combined dump path (.jsonl or .gz)."
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
        help=("Edge JSONL output path (default: data/etymyriad-edges.jsonl)."),
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
        default=DEFAULT_CROSSCHECK_LIMIT,
        help=(
            "Trees to fetch, one request per second "
            f"(default: {DEFAULT_CROSSCHECK_LIMIT})."
        ),
    )
    all_parser = subparsers.add_parser(
        "all", help="Parse, normalize, and load in one pass."
    )
    all_parser.add_argument(
        "--edges",
        help=(
            "Edge JSONL path, reused if it is newer than the dump "
            "(default: data/etymyriad-edges.jsonl)."
        ),
    )
    for edge_reader in (load_parser, crosscheck):
        edge_reader.add_argument(
            "--edges",
            help=(
                "Edge JSONL input path (default: data/etymyriad-edges.jsonl)."
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
    config = Config.from_env()
    usage_error = _resolve_usage(args, config)
    if usage_error is not None:
        print(usage_error, file=sys.stderr)
        return 2

    try:
        if args.command == "crosscheck":
            return _crosscheck(args, config)
        if args.command == "fetch-dump":
            return _fetch_dump()
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
    if args.command == "filter":
        return _missing_fields_error(args.input)
    needs_dump = {"parse", "normalize", "crosscheck"}
    if args.command in needs_dump and config.dump_path is None:
        return "no filtered dump in data/: run `etymyriad filter`"
    if args.command in needs_dump - {"parse"}:
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

    A dump with a sidecar, or at the default path, was trimmed by `filter`.
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
        if dump.resolve() != datafiles.data_path().resolve():
            return None
        sidecar = datafiles.fields_path(dump).name
        return f"{dump} has no {sidecar}: {_REFILTER}"
    missing = ", ".join(sorted(field_paths() - kept))
    if not missing:
        return None
    return f"{dump} lacks fields the parser reads ({missing}): {_REFILTER}"


def _served_dump_date() -> str:
    """Read the date of the dump kaikki.org serves now.

    Returns:
        The date, as YYYY-MM-DD.
    """
    _log.info("reading the dump date off kaikki.org")
    with httpx.Client(timeout=HTTP_TIMEOUT_SECONDS) as client:
        return served_dump_date(client)


def _local_dump_date() -> str:
    """Read the dump date that citations and tree fetches name.

    The raw dump's file name carries it, so a load cites the dump it
    was built from even if kaikki.org has published a newer one since.

    Returns:
        The date, as YYYY-MM-DD.

    Raises:
        ValueError: If no raw dump is on disk.
    """
    dump_date = datafiles.local_dump_date()
    if dump_date is None:
        msg = "no raw dump in data/: run `etymyriad fetch-dump`"
        raise ValueError(msg)
    _log.info("citing the enwiktionary dump dated %s", dump_date)
    return dump_date


def _filter_dump(source: str) -> int:
    """Write the filtered dump from a combined dump.

    Args:
        source: Combined dump path (.jsonl or .gz).

    Returns:
        How many entries were kept.
    """
    output = datafiles.data_path()
    entries = map(project_entry, filter_in_scope(stream_entries(source)))
    with datafiles.staged_path(output) as staged:
        written = _write_entries(staged, entries)
        datafiles.write_fields(output, field_paths())
    return written


def _ensure_raw_dump(dump_date: str) -> Path:
    """Download the raw dump unless one at least as new is on disk.

    Args:
        dump_date: The served dump's date, as YYYY-MM-DD.

    Returns:
        The newest raw dump's path.

    Raises:
        ValueError: If kaikki.org began serving another dump during the
            download, so the file would be named for the wrong date.
    """
    local_date = datafiles.local_dump_date()
    if local_date is not None and local_date >= dump_date:
        return datafiles.raw_dump_path(local_date)
    raw = datafiles.raw_dump_path(dump_date)
    _log.info("downloading the dump dated %s -> %s", dump_date, raw)
    with httpx.Client(timeout=HTTP_TIMEOUT_SECONDS) as client:
        download_raw_dump(client, raw)
    served_after = _served_dump_date()
    if served_after != dump_date:
        raw.unlink()
        msg = (
            f"kaikki.org moved from {dump_date} to {served_after} mid-download"
        )
        raise ValueError(msg)
    return raw


def _ensure_filtered_dump(dump_date: str) -> Path:
    """Bring the filtered dump up to date with what kaikki.org serves.

    Downloads the raw dump if needed, then filters it unless the
    filtered dump already postdates it.

    Args:
        dump_date: The served dump's date, as YYYY-MM-DD.

    Returns:
        The filtered dump's path.
    """
    raw = _ensure_raw_dump(dump_date)
    dump = datafiles.data_path()
    if not datafiles.is_current(dump, raw):
        _log.info("filtering %s -> %s", raw, dump)
        written = _filter_dump(str(raw))
        _log.info("filtered %s entries", _fmt(written))
    return dump


def _require_dump_path(config: Config) -> str:
    if config.dump_path is None:
        msg = "no dump to read"
        raise ValueError(msg)
    return config.dump_path


def _fetch_dump() -> int:
    """Run `fetch-dump`: print the path of the current raw dump.

    Returns:
        A process exit code (0 on success).
    """
    print(_ensure_raw_dump(_served_dump_date()))
    return 0


def _crosscheck(args: argparse.Namespace, config: Config) -> int:
    dump_date = _local_dump_date()
    index = graph_index(read_edges(args.edges))
    headwords = islice(
        tree_headwords(stream_entries(_require_dump_path(config))), args.limit
    )
    checked = edge_count = missing_count = 0
    with httpx.Client(timeout=HTTP_TIMEOUT_SECONDS) as client:
        for position, (headword, lang_code) in enumerate(headwords):
            if position:
                time.sleep(CROSSCHECK_FETCH_DELAY_SECONDS)
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


def _run_all(args: argparse.Namespace, config: Config) -> int:
    """Run `all`: fetch and filter the dump, normalize it, and load it.

    Returns:
        A process exit code (0 on success).
    """
    counts = Counter()
    dump = _ensure_filtered_dump(_served_dump_date())
    dump_date = _local_dump_date()
    fields_error = _missing_fields_error(str(dump))
    if fields_error is not None:
        print(fields_error, file=sys.stderr)
        return 2
    if not args.force_normalize and datafiles.is_current(
        Path(args.edges), dump
    ):
        _log.info("reusing edge file %s (skip normalize)", args.edges)
    else:
        _log.info("normalizing dump -> %s", args.edges)
        normalized = normalize(stream_entries(str(dump)))
        written = write_edges(args.edges, normalized)
        _log.info("normalized %s edges -> %s", _fmt(written), args.edges)
    _log.info("loading into %s", redact_dsn(config.database_url))
    loaded = load_edges(
        config.database_url,
        _tally_rel_types(read_edges(args.edges), counts),
        dump_date=dump_date,
        check_drift=not args.skip_sanity_gate,
    )
    _print_load_total(loaded, counts)
    _print_rel_type_breakdown(counts)
    return 0


def _dispatch(args: argparse.Namespace, config: Config) -> int:
    if args.command == "parse":
        count = sum(1 for _ in stream_entries(_require_dump_path(config)))
        print(f"parsed {_fmt(count)} entries")
        return 0

    if args.command == "filter":
        written = _filter_dump(args.input)
        print(f"filtered {_fmt(written)} entries -> {datafiles.data_path()}")
        return 0

    if args.command == "sync-languages":
        with httpx.Client(
            headers={"User-Agent": USER_AGENT},
            timeout=HTTP_TIMEOUT_SECONDS,
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
        dump_date = _local_dump_date()

        _log.info("loading into %s", redact_dsn(config.database_url))
        counts = Counter()
        loaded = load_edges(
            config.database_url,
            _tally_rel_types(read_edges(args.edges), counts),
            dump_date=dump_date,
            check_drift=not args.skip_sanity_gate,
        )
        _print_load_total(loaded, counts)
        _print_rel_type_breakdown(counts)
        return 0

    return _run_all(args, config)


if __name__ == "__main__":
    sys.exit(main())  # pragma: no cover
