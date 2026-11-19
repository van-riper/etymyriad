"""Decide which entries of the combined Wiktextract dump to keep.

kaikki.org publishes one dump for every language Wiktionary describes;
`filter` drops the entries whose language the registry cannot name
before `parse` or `normalize` ever see them.
"""

from etymyriad.languages._registry import resolve_language


def is_in_scope(code: str) -> bool:
    """Whether the registry knows a language code.

    Args:
        code: A Wiktionary language code.

    Returns:
        True if `code`, or the family prefix it starts with, resolves.
    """
    # Wiktionary prefixes custom codes with their family, so a code the
    # snapshot lost ("ine-grp-pro") still names its family up front.
    prefix = code.split("-", 1)[0]
    return (
        resolve_language(code) is not None
        or resolve_language(prefix) is not None
    )
