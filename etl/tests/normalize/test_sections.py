"""Tests for the claims an etymology section states about its links."""

from typing import TYPE_CHECKING

import msgspec

from etymyriad.model import SectionClaim, Term
from etymyriad.normalize import WiktextractEntry
from etymyriad.normalize import section_claims as claims_of_struct

if TYPE_CHECKING:
    from collections.abc import Iterator, Mapping


def section_claims(entry: Mapping[str, object]) -> Iterator[SectionClaim]:
    """Decode a dict entry, then read its section claims.

    Returns:
        The claims the entry's section states.
    """
    return claims_of_struct(msgspec.convert(entry, WiktextractEntry))


def test_unnumbered_entry_states_no_claims() -> None:
    """A page with one etymology has nothing to disambiguate."""
    entry = {
        "word": "or",
        "lang_code": "ang",
        "descendants": [{"lang_code": "enm", "word": "or"}],
    }

    assert list(section_claims(entry)) == []


def test_section_declares_its_ids() -> None:
    """Real record: en "or" Etymology 3 ("gold", heraldry)."""
    entry = {
        "word": "or",
        "lang_code": "en",
        "etymology_number": "3",
        "etymology_templates": [
            {"name": "etymid", "args": {"1": "en", "2": "gold"}},
            {"name": "etymon", "args": {"1": "en", "id": "tincture"}},
        ],
        "senses": [{"senseid": ["en:heraldry"]}],
    }

    assert {claim.wiktionary_id for claim in section_claims(entry)} == {
        "gold",
        "tincture",
        "heraldry",
    }


def test_section_lists_its_descendants_at_any_depth() -> None:
    """Real record: enm "or" Etymology 1, nested Descendants list."""
    entry = {
        "word": "or",
        "lang_code": "enm",
        "etymology_number": "1",
        "descendants": [
            {
                "lang_code": "en",
                "word": "or",
                "descendants": [{"lang_code": "sco", "word": "or"}],
            },
            {"lang_code": "yol", "word": "ar"},
        ],
    }
    page = Term("enm", "or", section=1)

    assert list(section_claims(entry)) == [
        SectionClaim(page, listed=Term("en", "or")),
        SectionClaim(page, listed=Term("sco", "or")),
        SectionClaim(page, listed=Term("yol", "ar")),
    ]


def test_section_lists_its_derived_terms_in_its_own_language() -> None:
    """Real record: en "-ly" Etymology 1 lists "friendly"."""
    entry = {
        "word": "-ly",
        "lang_code": "en",
        "etymology_number": "1",
        "derived": [{"word": "friendly"}],
    }

    assert list(section_claims(entry)) == [
        SectionClaim(
            Term("en", "-ly", section=1), listed=Term("en", "friendly")
        ),
    ]


def test_starred_descendant_lists_its_unstarred_term() -> None:
    """A listed proto-form keys on the same node its page does."""
    entry = {
        "word": "bʰer-",
        "lang_code": "ine-pro",
        "etymology_number": "1",
        "descendants": [{"lang_code": "gem-pro", "word": "*beraną"}],
    }

    [claim] = section_claims(entry)

    assert claim.listed is not None
    assert claim.listed.key == ("gem-pro", "beraną")


def test_korean_syllable_section_lists_its_hanja_readings() -> None:
    """Real record: ko 마 Etymology 7, the syllable's Hanja glosses."""
    table = "More information(eumhun reading: 삼 마 (sam ma))"
    entry = {
        "word": "마",
        "lang_code": "ko",
        "pos": "syllable",
        "etymology_number": "7",
        "senses": [
            {"glosses": [table, "麻: hemp; sesame"]},
            {"glosses": [table, "瑪"]},
            {"glosses": ["More information"]},
        ],
    }

    assert list(section_claims(entry)) == [
        SectionClaim(Term("ko", "마", section=7), reading="麻"),
        SectionClaim(Term("ko", "마", section=7), reading="瑪"),
    ]


def test_non_syllable_section_lists_no_readings() -> None:
    """Real record: ko 마 Etymology 3, a noun glossed with its Hanja."""
    entry = {
        "word": "마",
        "lang_code": "ko",
        "pos": "noun",
        "etymology_number": "3",
        "senses": [{"glosses": ["麻: hemp"]}],
    }

    assert list(section_claims(entry)) == []
