"""Command-line entry point: `etymyriad {parse,normalize,load,all}`."""

from __future__ import annotations

import argparse
import logging
import sys

from etymyriad.config import Config, redact_dsn, redact_secrets
from etymyriad.edgefile import read_edges, write_edges
from etymyriad.load import load_edges
from etymyriad.normalize import normalize
from etymyriad.parse import stream_entries

_DEFAULT_EDGES = "data/edges.jsonl"
_log = logging.getLogger(__name__)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="etymyriad")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("parse", help="Inspect the dump: count entries.")
    for name, verb in (("normalize", "output"), ("load", "input")):
        step = sub.add_parser(
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
    sub.add_parser("all", help="Parse, normalize, and load in one pass.")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the ETL.

    Args:
        argv: Command-line arguments, or None to read from the process args.

    Returns:
        A process exit code (0 on success).
    """
    args = _build_parser().parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
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

    if args.command == "normalize":
        edges = normalize(stream_entries(config.dump_path), config.dump_date)
        written = write_edges(args.edges, edges)
        print(f"normalized {written} edges -> {args.edges}")
        return 0

    if args.command == "load":
        _log.info("loading into %s", redact_dsn(config.database_url))
        loaded = load_edges(config.database_url, read_edges(args.edges))
        print(f"loaded {loaded} edges")
        return 0

    _log.info("loading into %s", redact_dsn(config.database_url))
    edges = normalize(stream_entries(config.dump_path), config.dump_date)
    loaded = load_edges(config.database_url, edges)
    print(f"loaded {loaded} edges")
    return 0


if __name__ == "__main__":
    sys.exit(main())  # pragma: no cover
