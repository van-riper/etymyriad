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
    "sa-cls": "cls",
    "sa-ved": "vsn",
    "roa-oan": "roa-ona",
    "grc-epc": "grc-epi",
    # Wiktionary files Khandeshi under Ahirani rather than ISO's "khn".
    "khn": "ahr",
})
