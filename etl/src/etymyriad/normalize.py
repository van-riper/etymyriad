"""Map raw Wiktextract entries to graph objects.

Each Wiktextract entry describes one word and carries `etymology_templates`:
structured records of the {{inh}}, {{bor}}, {{der}}, ... templates used on the
page. We translate those into directed `EtymEdge`s (ancestor -> the entry's own
lexeme).
"""

# NOTE: `_edges_from_entry` is the core parsing step and is intentionally a stub
# for now. The template-to-relation map below is real and is the validated
# contract it will build on (cross-checked against the Etymological Wordnet).

from __future__ import annotations

from typing import TYPE_CHECKING

from etymyriad.model import EtymEdge, Lexeme, RelType

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator

# Wiktextract template name -> our relation type.
TEMPLATE_RELS: dict[str, RelType] = {
    "inh": RelType.INHERITED,
    "inherited": RelType.INHERITED,
    "bor": RelType.BORROWED,
    "borrowed": RelType.BORROWED,
    "lbor": RelType.LEARNED_BORROWING,
    "slbor": RelType.SEMI_LEARNED_BORROWING,
    "der": RelType.DERIVED,
    "derived": RelType.DERIVED,
    "root": RelType.ROOT,
    "af": RelType.AFFIX,
    "affix": RelType.AFFIX,
    "prefix": RelType.AFFIX,
    "suffix": RelType.AFFIX,
    "com": RelType.COMPOUND,
    "compound": RelType.COMPOUND,
    "cal": RelType.CALQUE,
    "calque": RelType.CALQUE,
    "cog": RelType.COGNATE,
    "cognate": RelType.COGNATE,
    "m": RelType.MENTION,
    "mention": RelType.MENTION,
}


def normalize(entries: Iterable[dict]) -> Iterator[EtymEdge]:
    """Yield etymology edges for every entry in the stream."""
    for entry in entries:
        yield from _edges_from_entry(entry)


def lexeme_of_entry(entry: dict, dump_date: str) -> Lexeme:
    """Build the lexeme an entry describes (the descendant side).

    Args:
        entry: A parsed Wiktextract entry.
        dump_date: The enwiktionary dump date, pinned into source_ref.

    Returns:
        The lexeme the entry describes.
    """
    lang_code = entry.get("lang_code", "")
    raw = entry.get("word", "")
    starred = raw.startswith("*")
    headword = raw[1:] if starred else raw

    return Lexeme(
        lang_code=lang_code,
        headword=headword,
        gloss=_first_gloss(entry),
        pos=entry.get("pos"),
        is_reconstructed=starred or lang_code.endswith("-pro"),
        source_ref=f"wiktionary:{dump_date}:{lang_code}:{headword}",
    )


def _first_gloss(entry: dict) -> str | None:
    """Return the first sense's first gloss, or None if there is none."""
    for sense in entry.get("senses", []):
        glosses = sense.get("glosses")
        if glosses:
            return glosses[0]
    return None


def _edges_from_entry(entry: dict) -> Iterator[EtymEdge]:
    """Extract edges from one entry's etymology templates.

    Not yet implemented (cycle 5, see docs/backlog): this will read
    `entry["etymology_templates"]`, resolve each template's source
    language and term via `TEMPLATE_RELS` and the `etymon` handler,
    build the ancestor `Lexeme`, and yield ancestor -> entry edges,
    validated against the Etymological Wordnet.

    Args:
        entry: A parsed Wiktextract entry.

    Returns:
        An iterator over the etymology edges the entry yields.
    """
    _ = entry
    return iter(())
