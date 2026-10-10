"""Raw codes the dump uses that Wiktionary's live data does not define.

Shorthands are editor conveniences Wiktionary's templates accept. Drift
aliases cover codes Wiktionary removed or renamed after the dump was
built, matched by canonical name and sample headwords.
"""

from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping

    from etymyriad.languages._model import LanguageCode

SHORTHAND_ALIASES: Mapping[str, LanguageCode] = MappingProxyType({
    "EL.": "la-ecc",
    "LL.": "la-lat",
    "ML.": "la-med",
    "NL.": "la-new",
    "VL.": "la-vul",
})

DRIFT_ALIASES: Mapping[str, LanguageCode] = MappingProxyType({
    # Classical Sanskrit (e.g. अधार्मिक), now coded by ISO's "cls".
    "sa-cls": "cls",
    # Vedic Sanskrit (e.g. अभ्र), now coded by ISO's "vsn".
    "sa-ved": "vsn",
    # Old Navarro-Aragonese (e.g. arambre, cinco).
    "roa-oan": "roa-ona",
    # Epic Greek (e.g. ἄμαθος, Ἀχελώϊος).
    "grc-epc": "grc-epi",
    # Wiktionary files Khandeshi under Ahirani rather than ISO's "khn".
    "khn": "ahr",
})
