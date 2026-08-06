-- Migration 0005: composition-piece order on affix/root/compound edges.
--
-- Adds `piece_order`, the 1-based morpheme position an affix/root/
-- compound template gave an edge's ancestor (e.g. 1 for a prefix, 2
-- for the root it attaches to). NULL for a rel_type that never
-- decomposes a word into ordered pieces. Lets /tree order same-layer
-- etyma of one descendant to match the word's own composition instead
-- of alphabetically.

ALTER TABLE etymology ADD COLUMN piece_order SMALLINT;
