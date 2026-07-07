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


def lexeme_of_entry(entry: dict) -> Lexeme:
    """Build the lexeme an entry describes (the descendant side).

    Args:
        entry: A parsed Wiktextract entry.

    Returns:
        The lexeme the entry describes.
    """
    headword = entry.get("word", "")

    return Lexeme(
        lang_code=entry.get("lang_code", ""),
        headword=headword,
        pos=entry.get("pos"),
        is_reconstructed=headword.startswith("*"),
        source_ref=f"wiktionary:{entry.get('word', '')}",
    )


def _edges_from_entry(entry: dict) -> Iterator[EtymEdge]:
    """Extract edges from one entry's etymology templates.

    Args:
        entry: A parsed Wiktextract entry.

    Returns:
        An iterator over the etymology edges the entry yields.
    """
    return iter(())

    # TODO: read entry["etymology_templates"], resolve each template's source
    # language/term via TEMPLATE_RELS, build the ancestor Lexeme, and yield an
    # edge ancestor -> lexeme_of_entry(entry). Validate against Etymological
    # Wordnet before trusting the output.
