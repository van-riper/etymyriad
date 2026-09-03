-- Migration 0012: inflection relation type.
--
-- Inflected/non-lemma forms (e.g. la "adamantem") get their own dump
-- entry with a form_of pointer and no etymology_templates, so they
-- landed in the graph with descendants but no ancestors of their own.
-- This value lets the ETL emit lemma -> form edges for forms actually
-- cited as an ancestor elsewhere.

ALTER TYPE etym_rel_type ADD VALUE 'inflection';
