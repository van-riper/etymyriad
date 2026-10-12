"""Tests for the claims an etymology section states about its links."""

from __future__ import annotations

from etymyriad.model import SectionClaim, Term
from etymyriad.normalize import section_claims


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
