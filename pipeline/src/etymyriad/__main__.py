"""Command-line entry point: `etymyriad {parse,all}`."""

from __future__ import annotations

import argparse
import sys

from etymyriad.config import Config
from etymyriad.load import load_edges
from etymyriad.normalize import normalize
from etymyriad.parse import stream_entries


def main(argv: list[str] | None = None) -> int:
    """Run the pipeline.

    Args:
        argv: Command-line arguments, or None to read from the process args.

    Returns:
        A process exit code (0 on success).
    """
    parser = argparse.ArgumentParser(prog="etymyriad")
    parser.add_argument(
        "command",
        choices=("parse", "all"),
        help="'parse' inspects the dump. 'all' parses, normalizes, and loads.",
    )
    args = parser.parse_args(argv)
    config = Config.from_env()

    entries = stream_entries(config.dump_path)
    if args.command == "parse":
        count = sum(1 for _ in entries)
        print(f"parsed {count} entries")
        return 0

    loaded = load_edges(config.database_url, normalize(entries))
    print(f"loaded {loaded} edges")
    return 0


if __name__ == "__main__":
    sys.exit(main())
