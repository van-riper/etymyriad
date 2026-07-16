"""Command-line entry point: `etymyriad {parse,normalize,load,all}`."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from collections import Counter
from pathlib import Path
from typing import TYPE_CHECKING

from etymyriad.config import Config, redact_dsn, redact_secrets
from etymyriad.edgefile import read_edges, write_edges
from etymyriad.languages import filter_indo_european
from etymyriad.load import load_edges
from etymyriad.normalize import normalize
from etymyriad.parse import stream_entries

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator, Mapping

    from etymyriad.model import EtymEdge, RelType


_DEFAULT_EDGES = "data/edges.jsonl"
_DEFAULT_INE_OUTPUT = "data/raw/indo-european.jsonl"
_log = logging.getLogger(__name__)


def _add_checkpoint_arg(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--checkpoint",
        default=None,
        help=(
            "Resume checkpoint path: skips already-loaded edges on a "
            "restart and is updated after every committed chunk. Omit "
            "to load from scratch every run."
        ),
    )


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


def _tally_rel_types(
    edges: Iterable[EtymEdge], counts: Counter[RelType]
) -> Iterator[EtymEdge]:
    for edge in edges:
        counts[edge.rel_type] += 1
        yield edge


def _print_rel_type_breakdown(counts: Counter[RelType]) -> None:
    for rel_type, count in counts.most_common():
        print(f"  {rel_type}: {count}")


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
        if name == "load":
            _add_checkpoint_arg(step)
    all_parser = subparsers.add_parser(
        "all", help="Parse, normalize, and load in one pass."
    )
    _add_checkpoint_arg(all_parser)
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
    logging.basicConfig(level=level, format="%(levelname)s %(message)s")
    config = Config.from_env()

    try:
        return _dispatch(args, config)
    except Exception as e:  # noqa: BLE001 - last-resort DSN-safe guard
        _log.error("fatal: %s", redact_secrets(config.database_url, str(e)))
        return 1


def _dispatch(args: argparse.Namespace, config: Config) -> int:
    if args.command == "parse":
        count = sum(1 for _ in stream_entries(config.dump_path))
        print(f"parsed {count} entries")
        return 0

    if args.command == "filter-ine":
        entries = filter_indo_european(stream_entries(args.input))
        written = _write_entries(args.output, entries)
        print(f"filtered {written} Indo-European entries -> {args.output}")
        return 0

    if args.command == "normalize":
        counts: Counter[RelType] = Counter()
        edges = normalize(stream_entries(config.dump_path), config.dump_date)
        written = write_edges(args.edges, _tally_rel_types(edges, counts))
        print(f"normalized {written} edges -> {args.edges}")
        _print_rel_type_breakdown(counts)
        return 0

    if args.command == "load":
        _log.info("loading into %s", redact_dsn(config.database_url))
        counts = Counter()
        loaded = load_edges(
            config.database_url,
            _tally_rel_types(read_edges(args.edges), counts),
            checkpoint_path=args.checkpoint,
        )
        print(f"loaded {loaded} edges")
        _print_rel_type_breakdown(counts)
        return 0

    _log.info("loading into %s", redact_dsn(config.database_url))
    counts = Counter()
    edges = normalize(stream_entries(config.dump_path), config.dump_date)
    loaded = load_edges(
        config.database_url,
        _tally_rel_types(edges, counts),
        checkpoint_path=args.checkpoint,
    )
    print(f"loaded {loaded} edges")
    _print_rel_type_breakdown(counts)
    return 0


if __name__ == "__main__":
    sys.exit(main())  # pragma: no cover
