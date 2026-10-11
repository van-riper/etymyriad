"""Parse the <ety:...> chains nested inside an {{etymon}} term argument.

A term can carry its own ancestry inline, e.g.
"enm:marchaunt<ety:bor<xno:marchaunt<ety:der<la:mercāns>>>>": a keyword,
then one angle-wrapped term for each ancestor, each of which can carry a
chain of its own. A term with no language prefix takes its parent's
language.
"""

from __future__ import annotations

from typing import NamedTuple

from etymyriad.normalize._terms import _split_lang_prefix


class InlineRelation(NamedTuple):
    """One hop of an inline chain, ancestor to descendant.

    Attributes:
        src_lang: The ancestor's Wiktionary language code.
        src_term: The ancestor's term, as written.
        dst_lang: The descendant's Wiktionary language code.
        dst_term: The descendant's term, as written.
        keyword: The chain's relation keyword, e.g. "bor" or "af".
        piece_order: The ancestor's 1-based position among several
            ancestors under one keyword, or None for a single one.
    """

    src_lang: str
    src_term: str
    dst_lang: str
    dst_term: str
    keyword: str
    piece_order: int | None


def _groups(text: str) -> tuple[str, list[str]]:
    """Split "head<a><b<c>>" into its head and each top-level group.

    Args:
        text: A term or chain, possibly followed by angle-wrapped groups.

    Returns:
        The text before the first "<", and the contents of each balanced
        top-level "<...>" group after it. An unbalanced trailing group is
        dropped.
    """
    head_end = text.find("<")
    if head_end == -1:
        return text, []
    groups: list[str] = []
    depth = 0
    start = 0
    for index in range(head_end, len(text)):
        if text[index] == "<":
            if depth == 0:
                start = index + 1
            depth += 1
        elif text[index] == ">":
            depth -= 1
            if depth == 0:
                groups.append(text[start:index])
    return text[:head_end], groups


def _resolve(spec: str, default_lang: str) -> tuple[str, str, str | None]:
    """Read a term's language, term text, and inline chain.

    Args:
        spec: A term with optional "lang:" prefix and "<...>" modifiers.
        default_lang: The language to use when `spec` has no prefix.

    Returns:
        The language, the term (its alt text when it has none of its
        own), and the "<ety:...>" content, or None if there is none.
    """
    head, groups = _groups(spec)
    lang_code, term = _split_lang_prefix(head, default_lang)
    chain = None
    for group in groups:
        if group.startswith("alt:") and not term:
            term = group.removeprefix("alt:")
        elif group.startswith("ety:"):
            chain = group.removeprefix("ety:")
    return lang_code, term, chain


def inline_relations(spec: str, default_lang: str) -> list[InlineRelation]:
    """List every ancestor hop an inline chain states.

    Args:
        spec: A term argument, possibly carrying "<ety:...>" chains.
        default_lang: The language to use when `spec` has no prefix.

    Returns:
        One relation per ancestor under each chain, depth first. A term
        with no chain, or none that names a term, yields nothing.
    """
    lang_code, term, chain = _resolve(spec, default_lang)
    if chain is None or not term:
        return []
    keyword, children = _groups(chain)
    relations: list[InlineRelation] = []
    for position, child in enumerate(children, start=1):
        child_lang, child_term, _ = _resolve(child, lang_code)
        if not child_term:
            continue
        relations.append(
            InlineRelation(
                child_lang,
                child_term,
                lang_code,
                term,
                keyword.strip(),
                position if len(children) > 1 else None,
            )
        )
        relations.extend(inline_relations(child, lang_code))
    return relations
