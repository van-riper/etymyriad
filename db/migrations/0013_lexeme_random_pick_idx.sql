-- Migration 0013: index for randomLexeme's lang-filtered probe.
--
-- randomLexeme now probes lexeme_pkey directly (id > a random UUID)
-- instead of `ORDER BY random()`, which full-scans+sorts the whole
-- table. Unfiltered, that pkey probe is fast on its own. Filtered to
-- one language, it isn't: walking id order with lang_code as a plain
-- filter can cross most of the table before it finds a match in a
-- sparse language (measured 2.6s for 'kw', 425 of 778 candidates
-- reachable that way). This index lets Postgres seek straight to the
-- language's own id range instead.

CREATE INDEX lexeme_random_pick_idx ON lexeme (lang_code, id)
    WHERE NOT is_redlink AND degree > 0;
