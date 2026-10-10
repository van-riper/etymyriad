"""Load the etymology graph into Postgres.

Blue/green: every run rebuilds the whole graph from scratch in a `loading`
schema, then swaps it in for `public` atomically and drops the old
generation. There is no cross-run state: a run that fails before the swap
leaves `public` untouched and drops `loading`, and a run that succeeds
replaces `public` outright rather than upserting into it.
"""

from __future__ import annotations

from etymyriad.load._load import load_edges

__all__ = ["load_edges"]
