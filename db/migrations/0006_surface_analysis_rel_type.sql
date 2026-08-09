-- Migration 0006: surface-analysis relation type.
--
-- Adds 'surface_analysis' to etym_rel_type for {{surf}}, a same-language
-- morpheme decomposition Wiktionary templates that was previously
-- unmapped, so every {{surf}} template in the dump was silently
-- dropped instead of yielding edges (e.g. "homological" only showed
-- its {{der}} ancestor "ὁμός", never the {{surf}} piece "logical").

ALTER TYPE etym_rel_type ADD VALUE 'surface_analysis';
