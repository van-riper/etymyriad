"""Narrow the combined Wiktextract dump to the language families in scope.

kaikki.org publishes one dump for every language Wiktionary describes;
`filter` cuts it down to this project's scope before `parse` or
`normalize` ever see it.
"""

from etymyriad.config import SCOPE_FAMILIES
from etymyriad.languages._registry import resolve_language


def is_in_scope(code: str) -> bool:
    """Whether a language falls under a family in scope.

    Args:
        code: A Wiktionary language code.

    Returns:
        True if `code` resolves to a language whose Wiktionary lineage
        starts at a code in `SCOPE_FAMILIES`.
    """
    # Wiktionary prefixes custom codes with their family, so a code the
    # snapshot lost ("ine-grp-pro") still names its family up front.
    language = resolve_language(code) or resolve_language(code.split("-", 1)[0])
    if language is None or language.language_set is None:
        return False
    return language.language_set.path[0] in SCOPE_FAMILIES
