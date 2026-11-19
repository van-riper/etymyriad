# ETL refactor plan

A review of the `etl/` package's layout and test suite, with a plan to
restructure the first and cull the second. Reviewed at `a62787e`,
re-checked against `f39d600` (v0.5.4, 2026-10-12), and re-checked again
against `101d4a1` (v0.5.8, 2026-11-19). Line numbers below are as of
`101d4a1`. Nothing here has been done yet.

`feat/full-dump-scope` (5 commits, unmerged on 2026-11-19) rewrites
`is_in_scope`, the stub fold in `load/_merge.py`, and the strip rules in
`languages/`. Start the refactor after it merges, and re-check the
places marked "after full-dump-scope" below.

## Summary

The package splits by pipeline stage, and that split is sound. Three
things weaken it:

- `__main__.py` holds pipeline logic that belongs in library modules.
- `normalize/` spreads template knowledge over two files and term string
  cleanup over two more.
- Underscore names cross module lines 42 times, so an underscore no
  longer tells a reader what is private.

The test suite checks real behavior and fakes only real boundaries
(network, DB). It grew one test per bug, each with a hand-built 20-line
entry and a docstring that retells the bug. Some tests run the whole
pipeline to reach one branch because the logic sits in the wrong module.

| Verdict | Functions | Meaning                                      |
| ------- | --------- | -------------------------------------------- |
| KEEP    | 142       | core contract, or the only check on a branch |
| MERGE   | 152       | same branch as others; folds into ~49 tables |
| CUT     | 64        | redundant, restates a constant, tests a lib  |
| MOVE    | 12        | right check, wrong level or file             |

After the plan: about 200 test functions instead of 370, about 3.8K test
lines instead of 7.5K, and a suite of about 8s instead of 28s.

Since `f39d600` the suite gained 39 functions, almost all one per bug in
the old style: 60 docstrings in `test_edges.py` still open with "Real
record:". The cull is chasing a moving target, so the plan now puts the
lean-suite rules in `CLAUDE.md` before any test is cut (step 0).

Put simply, the code is cut into the right big pieces, but a few pieces
do their neighbors' work. Many tests check the same thing in different
words. A sixth can go now, and two fifths more fit into tables.

## Baseline

| Metric                | At `f39d600`          | At `101d4a1`          |
| --------------------- | --------------------- | --------------------- |
| Source lines (`src/`) | 5.5K                  | 5.7K                  |
| Test lines (`tests/`) | 6.7K                  | 7.5K                  |
| Test functions        | 331                   | 370                   |
| Collected cases       | 473, all pass         | 525, all pass         |
| Branch coverage       | 98%                   | 98%                   |
| Wall time             | 28 to 31s             | 28s                   |
| Of that, 2 swap tests | 20s                   | 20s                   |
| Biggest src file      | `_edges.py`, 842      | `_edges.py`, 945      |
| Biggest test file     | `test_edges.py`, 2239 | `test_edges.py`, 2542 |

75 of the 215 commits that touch `etl/tests` are `fix:` commits.

## Part 1: package layout

### Parts to keep

- The stage packages `normalize/`, `load/`, `languages/`, and
  `crosscheck/`, each with a small `__init__` that re-exports its public
  names.
- `model.py` as the single graph model, mirrored by `db/schema.sql`.
- `edgefile.py` as the intermediate format between normalize and load.
- The blue/green flow in `load/`. Its files (schema, staging, merge,
  finalize, swap) follow the pipeline steps.

### P1. `__main__.py` holds business logic

Of its 513 lines, about 200 are argparse, usage errors, dispatch, and
printing. The rest belongs elsewhere:

| Function in `__main__`                  | Belongs in                  |
| --------------------------------------- | --------------------------- |
| `_served_dump_date`, `_ensure_raw_dump` | `dump.py` (see P5)          |
| `_filter_dump`, `_write_entries`,       | `dump.py` (see P5)          |
| `_ensure_filtered_dump`                 |                             |
| `_default_edges` (mtime rules)          | `datafiles.py`              |
| `_missing_fields_error` (sidecar check) | `datafiles.py`              |
| `_local_dump_date` (raising wrapper)    | `datafiles.py`              |
| `_crosscheck` loop (fetch, sleep, diff) | `crosscheck/`               |
| load, print, and breakdown              | one helper (two copies now) |

This is the main reason `test_cli.py` runs to 1094 lines. About 20 CLI
tests set file mtimes and run `main()` to reach a single branch of
`_default_edges` or `_ensure_raw_dump`. `feat/full-dump-scope` adds a
dropped-language log to `_filter_dump`, so this part grows until it
moves.

### P2. Underscore names cross module lines

- `_edges.py` imports 12 underscore names from `_terms.py`, 2 from
  `_nodes.py`, and `_WiktextractSense`.
- `load/_load.py` imports 12 underscore names from all 5 of its
  siblings, and `_staging.py` and `_swap.py` read `_schema.py`'s schema
  name constants.
- `_nodes.py`, `_inline.py`, `_sections.py`, and `_normalize.py` import
  11 more between them.
- `_wiktextract.py` imports `model._MAX_SECTION`.

A `_module.py` file name already marks the module as private to its
package. Inside it, an underscore should mean "only this file uses
this". Today the underscore is on nearly everything, so a reader can't
tell the module's API to its siblings from its own helpers.

### P3. `normalize/_edges.py` repeats the template tables

- `TEMPLATE_REL_TYPES` holds the names in
  `_DIRECTIONAL_TEMPLATES | _AFFIX_FAMILY_TEMPLATES | _MENTION_TEMPLATES`
  plus `root`, which now has its own builder.
- Only the directional and affix builders read the map. Its mention
  and `root` entries are never read.
- A name added to a shape set but not to the map raises `KeyError` at
  run time. No test checks that the two agree.
- `_SINGLE_SOURCE_TEMPLATES` and `_ETYMON_SUB_REL_TYPES` share 10 keys.
- `_IGNORED_TEMPLATES`, `_MAPPED_TEMPLATES`, and
  `_unmapped_relation_names` (about 110 lines) exist only for the
  unmapped template log in `_normalize.py`.
- About 390 of the 945 lines are data.
- About 100 lines build edges from senses, not templates:
  `_edges_from_form_of`, `_edges_from_alt_of`, the gender label trim,
  `_ALT_FORM_BLOCKED_TAGS`, and the form-of sense checks.

Smaller point in the same file: builders take different arguments.
Some take `_TemplateContext`, others `(dst, anchor)`.

### P4. `normalize/_terms.py` mixes two concerns

- About 60% of `_terms.py` (379 lines) is affix, `{{surf}}`, and
  confix dash logic that only `_edges.py` uses. `_add_affix_dash` is
  the exception: `_nodes.py` uses it too, so it stays with the cleanup.
- The rest is raw string cleanup (star, PUA markers, inline annotations,
  `lang:` prefixes). `_nodes.py` turns that cleanup into `Term`s, so the
  two files share one job.
- There is no `test_terms.py`. The string parsing in `_lang_and_term`
  and its regex is tested only through the full edge dispatcher.

### P5. The dump stage is spread over five modules

- `kaikki.py` (156 lines): served date, download with retry and
  progress logging.
- `parse.py` (78 lines): `stream_entries`, a msgspec JSONL reader that
  skips redirects and malformed lines.
- `__main__.py`: ensure raw dump, ensure filtered dump, filter and
  write.
- `languages/_membership.py`: `is_in_scope`, called only by the filter.
- `datafiles.py`: the fields sidecar.

The first review moved `is_in_scope` into the dump module too, because
`config.SCOPE_FAMILIES` made `config` and `languages` import each other.
`feat/full-dump-scope` deletes `SCOPE_FAMILIES` and turns `is_in_scope`
into "the registry knows this code". That breaks the cycle and makes it
a registry question, so after full-dump-scope it stays in `languages/`.

### P6. Dead and test-only code

| Item                                    | Status                   |
| --------------------------------------- | ------------------------ |
| `languages.canonical_code`              | no callers, untested     |
| `languages.get_language_set`            | only tests call it       |
| `normalize.TEMPLATE_REL_TYPES` export   | only one test uses it    |
| `__main__._require_dump_path` raise     | unreachable              |
| `Config.dump_path`                      | re-probes `datafiles`    |
| `model.REL_TYPE_LABELS`, `RelTypeLabel` | no Python consumer       |
| `model.PROTO_LANG_SUFFIX`               | only `languages` uses it |
| 6 files in `tests/crosscheck/fixtures/` | unused, about 120 KB     |

The unused fixtures are `absquatulate`, `antidisestablishmentarianism`,
`buff`, `encyclopedia`, `incomprehensible`, and `myriad`.

`REL_TYPE_LABELS` claims to be the source for
`web/src/lib/shared/types.ts`, but no test compares the two copies, and
the web app is the only consumer. The proposal is to delete the Python
copy and make the TS copy canonical. That touches `web/`, so it is an
open decision below.

### P7. Smaller issues

- `_SWAP_SCHEMAS_SQL` bakes the 5s lock timeout in at import time. Tests
  can't shorten it, so the two swap-retry tests take 20s.
- `_resolve_usage` writes `args.edges` while it validates.
- Five `return`s in `_edges.py` (lines 572, 605, 642, 674, 726) drop a
  template that names no language, with no log line. No test reaches
  them. At minimum they should feed the unmapped template log.
- `kaikki.download_raw_dump`'s retry loop has a dead exit branch
  (`97->exit`): the last attempt either returns or raises. Writing it
  like `_swap_schemas` (retry N-1 times in the loop, then one final
  call) removes the dead branch.
- No test checks:
  - a diacritic stub with two real twins (the `HAVING` at
    `_merge.py` line 80). Re-check after full-dump-scope, whose
    `test_page_title_rule_never_merges_two_real_entries` may cover it.
  - `_run_all` with a current filtered dump but a bad sidecar
    (`__main__.py` lines 447 to 448)
  - `kaikki._format_size` in GiB (lines 78 to 79), the unit the real
    dump logs in
  - the unmapped log's handling of `{{ety}}`: it skips stringified
    copies and counts inline `<ety:>` keywords (`_edges.py` lines 877
    and 881 to 882). The unmapped log is a contract (rule 6).
  - `_lemma_page` for a lemma whose language the registry lacks
    (`_normalize.py` line 73)

The merge's self-loop filter had no test at `f39d600`.
`test_alias_folded_same_term_edge_is_dropped_and_logged` covers it now.

### Target layout

```text
etymyriad/
  __main__.py     argparse, usage errors, dispatch, printing (~200)
  config.py       constants, Config(database_url), redaction
  model.py        Term, EtymEdge, SectionClaim, RelType, MAX_SECTION
  datafiles.py    paths, staged_path, is_current, current_edge_file,
                  fields sidecar and its check, local_dump_date
  dump.py         NEW: kaikki.py + parse.py + filter code from
                  __main__ (served_dump_date, download_raw_dump
                  with its retry and progress log, ensure_raw_dump,
                  stream_entries, filter_dump with its dropped
                  language log, ensure_filtered_dump), ~380 lines
  edgefile.py     unchanged
  languages/      minus canonical_code and get_language_set; gains
                  PROTO_LANG_SUFFIX; keeps _membership.py
  normalize/
    _normalize.py   unchanged (stream facade, spool, lemma page
                    match, self-loop and unmapped logs)
    _templates.py   NEW: one name -> (shape, rel_type) catalog,
                    etymon codes, implied-language table, ignored
                    set, unmapped_relation_names
    _edges.py       template builders and dispatch only (~400)
    _forms.py       NEW: form_of and alt_of edges, gender label trim,
                    form-of sense checks (~100)
    _affix.py       NEW: affix/surf/confix dash rules from _terms.py
    _terms.py       string cleanup from _terms.py + _nodes.py
                    (term_of_entry, referenced_term, lang_and_term)
    _inline.py      unchanged
    _sections.py    unchanged
    _wiktextract.py unchanged; the form-of check becomes a property
                    on the sense model
  load/           same files; SQL built at call time
  crosscheck/     gains check_trees(): the fetch, sleep, diff loop
```

Naming rule for the whole package: in a `_module.py`, a name that a
sibling uses has no underscore. An underscore means "this file only".
Tests import from the package `__init__` where they can, and otherwise
only names without an underscore.

`dump.py` stays one flat module at about 380 lines. A `dump/` package
would add files without a reader who needs them.

Left as they are:

- The six files in `load/`. They map to pipeline steps; fixing the
  naming (P2) is enough.
- `edgefile.write_edges` and `read_edges`. They also carry terms and
  claims, so the names are slightly off, but renaming them would touch
  every caller for little gain.
- The four small files in `crosscheck/`, which are cohesive and well
  tested.
- `load/_load.py` reading `db/schema.sql` by relative path. That only
  works from a checkout, which is the only way the ETL runs.
- The two hand-written retry loops (`download_raw_dump`,
  `_swap_schemas`). Two copies don't justify a shared helper.

## Part 2: the test cull

### Method

Three subagents read all 327 test functions at `a62787e` and sorted each
one into KEEP, MERGE, CUT, or MOVE. They checked each CUT by running
branch coverage with it deselected. The 4 tests added to `test_kaikki.py`
since then were classified by hand: the two retry tests are KEEP, and
the two progress-log tests form one MERGE group.

Deselecting all 65 CUT tests leaves every module's coverage unchanged,
except for three spots that are safe to lose:

- `languages/_membership.py`: the CLI filter test still covers it.
- `languages/_registry.py` line 216: `get_language_set`, which P6
  deletes.
- `load/_staging.py` lines 191 to 192: a progress log line.

At `101d4a1`, two of the 65 are gone (`f9dbbe1` and `f76bbda` removed
them) and one new test joins the list. The 56 tests
added since `f39d600` were classified by hand (Appendix D). Deselecting
the 63 surviving CUTs again lost only `_registry.py` line 216 and
`_staging.py` lines 191 to 192.

Coverage records which lines ran. It does not record which results a
test asserted, so a deleted test can be the only one that checks a value
on a line other tests also run. Those cases are listed under "Checks
that must not lapse" and ship with the change that would drop them.

### Where the bulk comes from

- `test_edges.py` writes a full entry dict 66 times, 12 to 20 lines
  each. Its 5 overlapping helpers (from line 1737 on) serve only the
  tests below them.
- Docstrings in `test_edges.py` take 353 lines, mostly "Real record:"
  narration and bug history.
- Logic in the wrong module (P1, P4) forces whole-pipeline setup for
  checks of a single branch.

### What gets cut

| Kind                            | Count | Example                   |
| ------------------------------- | ----- | ------------------------- |
| Same branch as another test     | 32    | `*_strips_inline_id_*`    |
| Upstream data facts, not code   | 9     | `test_registry_data.py`   |
| Retired names or removed bugs   | 8     | `test_filter_ine_is_gone` |
| Restates a constant or enum     | 7     | `test_template_map_*`     |
| Tests a library or Postgres DDL | 5     | `test_filter_has_no_*`    |
| Log format only                 | 4     | `test_fmt_uses_*`         |

Some tests fit two kinds, so the counts are approximate. Appendix A
lists every CUT test.

### Rules to keep the suite lean

Add these to the TDD section of `CLAUDE.md` before the cull starts
(step 0), so new tests stop adding to the pile:

1. A bug fix adds a row, not a test. Add a new test function only when
   the fix adds a new branch. Name the row after the real record
   (`id="hrx-China"`) instead of retelling it in a docstring.
2. Test at the entry point, except for dense string parsing. Edge
   behavior goes through `_edges_from_entry` or `normalize()`. Load
   behavior goes through `load_edges` and the final `public` tables.
   String helpers with many input shapes (`lang_and_term`,
   `section_of`) get their own table test.
3. Don't restate a constant. The exceptions are mirrors across
   artifacts: the SQL enum and `RelType`, the baseline migration and
   `schema.sql`, and (new) the template catalog and the ignore list.
4. Don't test a library: argparse, httpx `raise_for_status`,
   `json.loads`, or Postgres enforcing declared DDL.
5. Upstream data gets invariants only. Keep "every dump code resolves"
   and "drift aliases never shadow a live code". Drop "English has this
   6-level hierarchy".
6. Test a log only when it is a contract. The unmapped template log, DSN
   redaction, and the dump download progress (the only feedback during
   a long download) count. A progress log in each module gets one table
   at most. Number formatting helpers get none.
7. One-line docstrings. History belongs in git.

### Checks that must not lapse

These results are checked only by a test the plan cuts or merges.
Coverage won't flag their loss, so each ships in the same commit as that
cut or merge. "Blind" means coverage.py can't see the branch at all,
since it is a short-circuit inside one `if`.

| Check                                 | Checked only by      | Lands with   |
| ------------------------------------- | -------------------- | ------------ |
| `{{etymon}}` `:root` maps to `ROOT`   | a CUT test           | the cut      |
| `{{etymon}}` `:af` gives AFFIX pieces | a MERGE test         | the G5 table |
| crosscheck skips a `None` tree        | a MERGE test         | that merge   |
| `redact_dsn` on a DSN with no port    | a MERGE test         | that merge   |
| `all --force-normalize` re-parses     | a MERGE test (blind) | that merge   |

Each cull commit names in its body what every deleted test asserted,
and points to the surviving test that asserts it, or adds that row in
the same commit.

### Gaps nothing checks today

These are new tests rather than replacements, so they can wait for
Phase 2:

- a diacritic stub with two real twins, unless full-dump-scope covers it
- a blank line in `stream_entries` and `read_edges`
- `_format_size` in GiB
- the unmapped log's `{{ety}}` stringified copy and inline keywords
- `_lemma_page` for an unregistered language

## Plan

Each step is one atomic commit or a short series, and the suite stays
green throughout. Check coverage after each step with
`COVERAGE_FILE=/tmp/etl-cov uv run pytest --cov --cov-branch`. Use a
private coverage file, because parallel runs that share `.coverage`
corrupt each other's data.

### Phase 0: freeze the target

0. Wait for `feat/full-dump-scope` to merge, then re-check this plan
   against it (see Handoff notes). Add the rules from "Rules to keep
   the suite lean" to `CLAUDE.md` in their own commit.

### Phase 1: cut and delete

No source logic changes in this phase.

1. Delete the 64 CUT tests, one commit per package. The `test_edges.py`
   commit adds the `:root` row to the existing
   `test_etymon_keyword_maps_to_its_relation`.
2. Delete the dead code from P6 and the 6 unused fixtures. The
   `REL_TYPE_LABELS` part waits on its open decision.

Expected result: about 306 functions, coverage unchanged, and every
check in "Checks that must not lapse" still asserted somewhere.

### Phase 2: fold tests into tables

3. Write one `entry(...)` builder for `tests/normalize/` and rewrite
   `test_edges.py` on top of it as merge groups G1 to G9 (Appendix B).
   The file should shrink from 2542 lines to about 1000.
4. Fold the other merge groups. Each merge keeps its rows from "Checks
   that must not lapse" as explicit parameters. Add the tests from
   "Gaps nothing checks today".

Expected result: about 200 functions, coverage at 98% or higher.

### Phase 3: restructure the source

This is refactoring under green tests. For logic that moves, TDD still
applies: write the unit test at the new location first, watch it fail on
the missing name, then move the code and delete the CLI tests it
replaces.

5. Rename the cross-module underscore names (P2). Mechanical.
6. Build the swap SQL at call time and shorten the lock timeout in the
   retry test. Saves about 20s.
7. Move logic out of `__main__` into `datafiles.py`, `dump.py`, and
   `crosscheck/` (P1, P5). `test_kaikki.py`, `test_parse.py`, and the
   CLI filter tests become `test_dump.py`. `test_cli.py` keeps one smoke
   test per subcommand, the exit-2 usage errors, and DSN redaction, and
   shrinks from 1094 lines to about 400.
8. Split normalize into `_templates.py` (one catalog), `_forms.py`,
   `_affix.py`, and a `_terms.py` merged with `_nodes.py` (P3, P4). Add
   `test_terms.py` for the moved string cases. The gender label rows of
   the lemma page table become a unit table in a `test_forms.py`.
9. Switch `test_merge.py` from its private `_merge` harness to
   `load_edges` plus queries on `public`. The unknown-language test is
   the exception; it asserts the gate's error instead.

### Phase 4: docs

10. Update `docs/ARCHITECTURE.md`. Line 230 names `_IGNORED_TEMPLATES`
    in `normalize/_edges.py`, and line 69 names
    `etl/tests/load/test_schema.py`.

Cutting comes first so the restructure has fewer tests to move. Folding
comes before restructuring so each moved behavior has one table to
update instead of five tests.

### Open decisions

| Question                                    | Proposed default      |
| ------------------------------------------- | --------------------- |
| Delete Python `REL_TYPE_LABELS`; TS owns it | yes                   |
| Silent no-language `return`s in `_edges.py` | count them in the log |
| `Config` keeps only `database_url`          | yes                   |
| Keep data facts in `test_registry_data.py`  | no, keep 2 invariants |
| Move form_of/alt_of edges to `_forms.py`    | yes                   |
| Lean rules in `CLAUDE.md` before the cull   | yes                   |

## Appendix A: CUT list (64)

`tests/normalize/test_edges.py` (17):

- `test_template_map_covers_core_relations`
- `test_directional_strips_inline_id_annotation_from_term`
- `test_same_language_affix_piece_carries_no_section`
- `test_etymon_inh_relation_matches_sibling_inh_template`
- `test_etymon_from_relation_with_explicit_lang_prefix`
- `test_etymon_strips_inline_id_annotation_from_term`
- `test_directional_template_edge_carries_no_piece_order`
- `test_compound_template_yields_one_edge_per_morpheme`
- `test_suf_and_infix_gaps_are_filled`
- `test_affix_family_strips_inline_id_annotation_from_term`
- `test_etymon_af_relation_yields_one_edge_per_morpheme_beyond_two`
- `test_etymon_single_term_relation_carries_no_piece_order`
- `test_mention_strips_inline_id_annotation_from_term`
- `test_m_plus_falls_back_to_base_term`
- `test_dercat_yields_no_edge_even_with_a_non_language_second_arg`
- `test_surf_template_yields_one_edge_per_morpheme`
- `test_surf_lang_specific_type_flag_yields_one_edge_per_morpheme`

`tests/test_cli.py` (9):

- `test_fmt_uses_thousands_separators`
- `test_rel_type_breakdown_uses_thousands_separators`
- `test_filter_has_no_output_flag`
- `test_filter_ine_is_gone`
- `test_readers_ignore_wiktextract_dump`
- `test_normalize_never_reads_the_dump_date`
- `test_debug_flag_sets_the_root_log_level`
- `test_all_skips_the_download_when_the_local_dump_is_current`
- `test_normalize_replaces_the_previous_edge_file`

Other top-level files (8):

- `test_config.py::test_dump_env_is_ignored`
- `test_datafiles.py::test_paths_are_fixed_names_in_the_data_dir`
- `test_edgefile.py::test_write_edges_leaves_no_temp_file`
- `test_edgefile.py::test_reads_an_edge_file_with_sorted_spaced_keys`:
  spacing and key order are msgspec's job, and
  `test_writes_compact_utf8_lines` pins the field names
- `test_kaikki.py::test_a_server_error_raises`
- `test_model.py::test_rel_type_labels_cover_every_rel_type`
- `test_model.py::test_rel_type_labels_are_nonempty_and_distinct`
- `test_model.py::test_rel_types_match_what_normalize_can_emit`

`tests/load/` (7):

- `test_load.py::test_log_progress_uses_thousands_separators`
- `test_merge.py::test_dataset_records_the_dump_date`
- `test_schema.py::test_dataset_holds_one_row`
- `test_schema.py::test_no_extension_schema`
- `test_staging.py::test_stages_an_edge_and_both_terms`
- `test_staging.py::test_stage_items_progress_log_includes_a_rate`
- `test_swap.py::test_swap_schemas_promotes_loading`

`tests/languages/` (12):

- `test_membership.py::test_scope_follows_scope_families` (full-dump-scope
  deletes it anyway)
- `test_registry_data.py`: every test except
  `test_every_dump_code_resolves` and
  `test_drift_aliases_only_cover_removed_codes` (9)
- `test_registry.py::test_split_variety`
- `test_sources.py::test_fetch_wikidata_iso_rejects_html_error_page`

`tests/crosscheck/` (2):

- `test_report.py::test_headword_repeats_once_per_entry`
- `test_tree.py::test_compound_tree_joins_both_branches`

`tests/normalize/`, other files (9):

- `test_inline.py::test_affix_chain_nested_inside_another_chain`
- `test_inline.py::test_modifier_text_with_commas_does_not_split_the_term`
- `test_nodes.py::test_term_carries_section_and_one_sense`
- `test_nodes.py::test_term_section_is_zero_when_not_given`
- `test_nodes.py::test_reconstructed_headword_is_flagged`
- `test_nodes.py::test_referenced_code_resolves_to_full_language_and_variety`
- `test_normalize.py::test_form_of_page_merges_with_its_homograph_lemma`
- `test_normalize.py::test_normalize_yields_solo_entirely_form_of_entry`
- `test_normalize.py::test_normalize_mixed_entry_inflection_edge_keeps_its_own_key`

Total: 17 + 9 + 8 + 7 + 12 + 2 + 9 = 64.

Two CUTs from `f39d600` are already gone:
`test_same_word_der_template_yields_no_self_loop_edge` and
`test_filter_in_scope_keeps_only_matching_entries`.

## Appendix B: merge groups (152 tests)

Each group becomes one test, usually parametrized. Tests outside
Appendices A to C are KEEP.

### `tests/normalize/test_edges.py` (42)

G1, no term yields no edge (`-` or empty):

- `test_directional_literal_dash_term_yields_no_edge`
- `test_etymon_literal_dash_term_yields_no_edge`
- `test_affix_family_skips_a_literal_dash_piece`
- `test_mention_literal_dash_term_yields_no_edge`
- `test_single_source_template_without_a_term_yields_nothing`

G2, affix dash side and base piece (add the two confix rows from
`test_piece_template_yields_ordered_pieces`):

- `test_prefix_template_yields_one_edge_per_morpheme`
- `test_affix_family_skips_a_missing_piece`
- `test_suffix_template_adds_missing_dash`
- `test_prefix_template_chain_adds_missing_dash_except_on_base`
- `test_infix_template_adds_missing_leading_and_trailing_dash`

G3, `{{surf}}` `+type` flag offset and dash:

- `test_surf_template_type_flag_is_not_a_language`
- `test_surf_suffix_flag_adds_missing_dash`
- `test_surf_prefix_flag_adds_missing_dash`
- `test_surf_confix_flag_adds_missing_dashes`
- `test_surf_lang_specific_type_flag_has_no_language_arg`

G4, template name to relation catalog (keep 1 or 2 ignored rows):

- `test_non_ancestor_templates_yield_no_edge`
- `test_directional_alias_template_yields_its_relation`
- `test_piece_template_yields_ordered_pieces`
- `test_single_source_template_yields_its_relation`
- `test_spelling_alias_template_yields_its_relation`
- `test_leftover_template_yields_its_relation`

G5, etymon keywords and grouping (add `:root`; keep `:af`):

- `test_etymon_strips_uncertainty_annotation_from_relation_code`
- `test_etymon_af_relation_yields_one_edge_per_morpheme`
- `test_etymon_keyword_maps_to_its_relation`
- `test_etymon_psm_code_maps_to_borrowed`

G6, inline `<ety:>` chain hops and their anchor:

- `test_etymon_inline_chain_yields_an_edge_per_hop`
- `test_etymon_inline_affix_hop_carries_piece_order`
- `test_etymon_inline_hop_shares_the_templates_anchor`
- `test_inline_chain_uses_the_same_keyword_map`

G7, `//` alternants (keep the affix piece order and etymon chain rows):

- `test_directional_double_slash_yields_one_edge_per_alternant`
- `test_single_source_double_slash_yields_one_edge_per_alternant`
- `test_affix_double_slash_alternants_share_a_piece_order`
- `test_etymon_double_slash_splits_the_term_and_its_chain`
- `test_double_slash_drops_an_empty_alternant`

G8, link target in args 3, shown text in args 4:

- `test_directional_links_args3_not_its_display_text`
- `test_directional_falls_back_to_args4_when_args3_is_empty`
- `test_der_links_args3_even_when_args4_shows_another_form`

G9, alt_of senses (one edge row, four no-edge rows):

- `test_alt_of_yields_alt_form_edge_to_variant`
- `test_alt_of_keeps_standard_spelling_without_alternative_tag`
- `test_alt_of_without_alt_of_tag_yields_no_edge`
- `test_alt_of_with_blocked_tag_yields_no_edge`
- `test_alt_of_multiword_target_yields_no_edge`

### `tests/test_cli.py` (26)

Most of these become unit tests of the moved logic in Phase 3.

- normalize output path: `test_normalize_writes_edge_file`,
  `test_normalize_writes_the_default_edge_file`
- load to loader: `test_load_passes_edges_and_dump_date_to_the_loader`,
  `test_load_cites_the_local_raw_dump_date`,
  `test_load_passes_the_gate_flag`
- `all` happy path: `test_all_passes_the_gate_flag`,
  `test_all_writes_edges_file_and_loads_it`,
  `test_all_normalizes_into_the_default_edge_file`
- `all` download: `test_all_downloads_and_filters_when_nothing_is_local`,
  `test_all_downloads_when_the_served_dump_is_newer`
- `all` edge reuse: `test_all_reuses_an_existing_edge_file`,
  `test_all_reuses_a_current_default_edge_file`
- `all` renormalize (keep `--force-normalize` as a row):
  `test_all_force_normalize_rebuilds_an_existing_edge_file`,
  `test_all_renormalizes_an_edge_file_older_than_its_dump`
- crosscheck (keep a `None` tree row):
  `test_crosscheck_reports_tree_edges_the_graph_lacks`,
  `test_crosscheck_fetches_trees_as_of_the_local_dump_date`
- default edge file: `test_load_defaults_to_the_current_edge_file`,
  `test_load_refuses_an_edge_file_older_than_its_dump`,
  `test_load_refuses_edges_older_than_the_raw_dump`,
  `test_load_without_a_dump_reads_the_edge_file`,
  `test_edge_readers_exit_2_without_an_edge_file`
- fields guard:
  `test_normalize_refuses_a_filtered_dump_without_a_sidecar`,
  `test_normalize_refuses_a_dump_missing_a_parsed_field`,
  `test_normalize_accepts_a_sidecar_with_retired_fields`,
  `test_filter_refuses_a_trimmed_input_missing_parsed_fields`,
  `test_filter_refuses_a_sidecarless_dump_named_relatively`

### Other top-level files (16)

- `redact_dsn` (add a no-port row): `test_config.py::`
  `test_redact_dsn_masks_password`,
  `test_redact_dsn_without_password_is_unchanged`
- `dump_path` (drops out if `Config` loses the field):
  `test_config.py::test_from_env_defaults_dump_path_to_the_filtered_dump`,
  `test_config.py::test_dump_path_is_none_without_a_dump`
- `is_current`, newer, equal, older, missing: `test_datafiles.py::`
  `test_is_current_when_the_edge_file_is_no_older`,
  `test_is_not_current_when_the_dump_is_newer`,
  `test_is_current_is_false_for_a_missing_edge_file`
- edge file progress log: `test_edgefile.py::`
  `test_write_edges_logs_progress_periodically`,
  `test_write_edges_does_not_repeat_a_final_periodic_log`,
  `test_write_edges_progress_log_includes_a_rate`
- download progress log, known and unknown size: `test_kaikki.py::`
  `test_download_logs_progress_against_the_known_size`,
  `test_download_logs_progress_without_a_known_size`
- SectionClaim validation: `test_model.py::`
  `test_section_claim_needs_a_numbered_section`,
  `test_section_claim_states_exactly_one_thing`
- skipped dump lines (add a blank line row): `test_parse.py::`
  `test_stream_skips_malformed_lines`,
  `test_stream_logs_malformed_line_number`,
  `test_stream_skips_an_entry_naming_no_word`,
  `test_stream_skips_a_redirect_quietly`

### load, languages, crosscheck, normalize (66)

- end-to-end load, anchored on the KEEP test
  `test_load.py::test_load_edges_runs_full_pipeline_and_returns_edge_count`
  (also absorbs a MOVE, see Appendix C):
  `test_finalize.py::test_pickable_terms_skip_redlinks_and_mention_only_terms`,
  `test_merge.py::test_staging_tables_are_dropped`,
  `test_swap.py::test_swap_replaces_public_and_keeps_no_old_copy`
- failed load: `test_finalize.py::test_failed_load_drops_the_loading_schema`,
  `test_swap.py::test_failed_gate_leaves_public_untouched`
- swap retry (needs the P7 timeout fix):
  `test_swap.py::test_swap_schemas_retries_after_a_lock_timeout`,
  `test_swap.py::test_swap_schemas_gives_up_after_three_attempts`
- diacritic alias (add the two-twin row; re-check after
  full-dump-scope, which adds three page-title rule tests here):
  `test_merge.py::`
  `test_diacritic_stub_folds_into_its_unique_real_twin`,
  `test_diacritic_stub_folds_into_its_unmarked_stub_twin`,
  `test_real_twin_beats_an_unmarked_stub_twin`,
  `test_reconstructed_stub_keeps_its_macron`
- undeclared id log: `test_merge.py::test_undeclared_id_is_logged`,
  `test_id_on_a_single_section_page_is_not_logged`
- duplicate edge: `test_merge.py::`
  `test_duplicate_edges_keep_the_lowest_anchor`,
  `test_duplicate_edges_keep_one_templates_provenance`
- ISO join: `test_snapshot_build.py::`
  `test_two_letter_code_joins_through_its_iso639_1_item`,
  `test_deprecated_two_letter_code_keeps_only_iso639_1`,
  `test_bibliographic_code_is_the_iso639_2_value_that_differs`,
  `test_three_letter_code_needs_wikidata_confirmation`,
  `test_custom_code_never_borrows_its_qid_items_iso_code`
- page title rule: `test_registry.py::`
  `test_strip_diacritics_follows_the_language_rule`,
  `test_strip_diacritics_without_a_rule_keeps_text`
- strip rule parsing (re-check after full-dump-scope, which renames one
  and adds three more): `test_snapshot_build.py::`
  `test_strip_rule_keeps_marks_and_exceptions`,
  `test_strip_rule_merges_every_script`,
  `test_strip_rule_reads_exceptions_sent_as_a_list`,
  `test_strip_rule_skips_lua_pattern_exceptions`,
  `test_strip_rule_in_a_module_is_skipped`
- sync failure: `test_sources.py::`
  `test_sync_snapshot_leaves_file_untouched_on_failure`,
  `test_sync_snapshot_refuses_a_snapshot_the_registry_cannot_link`
- tree selection: `test_fetch.py::test_tree_of_another_language_is_skipped`,
  `test_fetch.py::test_first_tree_of_the_language_wins`
- no tree flag: `test_report.py::test_entry_without_a_tree_flag_is_skipped`,
  `test_report.py::test_other_template_with_a_tree_arg_is_skipped`
- inline default language: `test_inline.py::`
  `test_unprefixed_child_takes_its_parents_language`,
  `test_unprefixed_top_level_term_takes_the_default_language`
- inline modifier children: `test_inline.py::`
  `test_dash_placeholder_child_is_not_a_term`,
  `test_literal_gloss_modifier_child_is_not_a_term`,
  `test_uncertain_modifier_child_is_not_a_term`,
  `test_language_code_that_matches_a_modifier_stays_a_term`
- decoding trims to the Struct: `test_wiktextract.py::`
  `test_decoding_drops_undeclared_keys`,
  `test_decoding_trims_nested_structs`,
  `test_decoding_trims_descendants_at_every_depth`
- first gloss: `test_nodes.py::test_gloss_read_from_first_sense`,
  `test_nodes.py::test_gloss_absent_when_no_senses`
- reconstructed flag: `test_nodes.py::`
  `test_proto_own_entry_is_reconstructed_without_star`,
  `test_starred_headword_is_normalized`,
  `test_plain_headword_is_not_reconstructed`,
  `test_reconstruction_namespace_entry_is_reconstructed`,
  `test_mainspace_entry_of_attested_proto_language_is_not`
- variety reference: `test_nodes.py::`
  `test_referenced_provencal_is_not_reconstructed`,
  `test_variety_reference_lands_on_the_full_language`,
  `test_reconstructed_variety_reference_is_reconstructed`
- referenced term cleanup, folding in the `<id:>` cases the CUT
  `*_strips_inline_id_*` tests had:
  `test_nodes.py::test_referenced_term_drops_whitespace_before_annotation`
- form to lemma page (step 8 splits the gender rows off):
  `test_normalize.py::`
  `test_normalize_yields_inflection_edge_when_the_lemma_has_a_page`,
  `test_normalize_drops_inflection_edge_when_the_lemma_has_no_page`,
  `test_stress_marked_lemma_links_to_its_page_title`,
  `test_lemma_with_a_page_as_cited_keeps_its_marks`,
  `test_lemma_cited_with_a_gender_label_links_to_its_page`,
  `test_label_letters_inside_a_word_are_kept`,
  `test_alt_form_edge_kept_when_main_form_has_no_page`
- self-loop drop and its log: `test_normalize.py::`
  `test_normalize_drops_an_edge_from_a_term_to_itself`,
  `test_normalize_logs_dropped_self_loops_by_kind`
- unmapped log: `test_normalize.py::`
  `test_normalize_logs_a_template_it_neither_maps_nor_ignores`,
  `test_normalize_logs_an_unmapped_etymon_code`
- ignored template, 1 or 2 rows: `test_normalize.py::`
  `test_normalize_does_not_log_an_ignored_template`,
  `test_template_with_no_ancestry_is_ignored`

## Appendix C: MOVE list (12)

| Test                                             | To                    |
| ------------------------------------------------ | --------------------- |
| `test_referenced_term_strips_*_markers`          | `test_terms.py`       |
| `test_directional_latin_period_shorthand_*`      | `lang_and_term` table |
| `test_referenced_term_carries_no_senses`         | `test_terms.py`       |
| `test_etymon_af_term_with_embedded_colon_*`      | `lang_and_term` table |
| `test_etymon_wiki_interlink_prefix_is_not_a_*`   | `lang_and_term` table |
| `test_affix_piece_with_latin_period_shorthand_*` | `lang_and_term` table |
| `test_etymon_af_piece_written_only_as_alt_*`     | `lang_and_term` table |
| `test_filter_reports_a_missing_input`            | `test_dump.py`        |
| `test_filter_writes_compact_utf8_lines`          | `test_dump.py`        |
| `test_drift_gate_skips_when_public_*`            | end-to-end load test  |
| `test_edge_rejects_a_same_term_edge`             | `test_alias_folded_*` |
| `test_ignored_templates_overlap_no_mapped_*`     | `test_templates.py`   |

The first seven are in `test_edges.py`. The rest come from
`test_cli.py` (two), `test_finalize.py`, `test_schema.py`, and
`test_normalize.py`, in that order. Some of the `lang_and_term` rows are
the only checks on `_terms.py` lines 139 to 141 and 173 to 174, so
they move rather than go.

## Handoff notes

Context for whoever starts the refactor:

- Start from a fresh branch off local `main`, not `origin/main`, after
  `feat/full-dump-scope` merges. Re-check this plan against any `etl/`
  commits after `101d4a1` first: `git log 101d4a1..main -- etl/`. New
  tests need a verdict, and line numbers may have moved.
- The surviving 63 CUT tests from `f39d600` were deselected together
  on `101d4a1`: the only coverage lost is `_registry.py` line 216 and
  `_staging.py` lines 191 to 192, as expected. If `etl/` has changed
  since, re-run that check and compare per-module misses with a full
  run:

  ```sh
  cd etl
  COVERAGE_FILE=/tmp/etl-cov uv run pytest --cov=etymyriad \
    --cov-branch --cov-report=term-missing --deselect <test-id> ...
  ```

- The DB tests spawn their own Postgres through pytest-postgresql, using
  `/usr/bin/pg_ctl`. They need no running local DB.
- Ask the owner about the open decisions before step 2 (the
  `REL_TYPE_LABELS` deletion) and step 7 (`Config.dump_path`).
- `CLAUDE.md`'s TDD section mentions golden tests, but the ETL has none;
  the closest is `crosscheck/test_tree.py`'s `wine` fixture. Adding a
  golden corpus was considered and left out. The tables in Appendix B
  pin the same behavior with less upkeep.
- The project board (`gh project ... 4 --owner van-riper`) has no item
  for this work yet. Add one per phase when it starts, and keep ticket
  IDs out of commit messages and code comments.
- Subagents may help with the mechanical steps (1, 3, 5), but they must
  not commit. Review and commit their work in the main session.

## Appendix D: tests added after f39d600 (56)

Three are renames of tests the plan already sorted:
`test_load_edges_runs_full_pipeline_and_returns_edge_count` (KEEP) and
the two inflection tests now in "form to lemma page" (MERGE). The other
53 split like this. Their MERGE groups are in Appendix B, the one CUT in
Appendix A, and the one MOVE in Appendix C.

| Verdict | Count | Tests                                             |
| ------- | ----- | ------------------------------------------------- |
| KEEP    | 11    | see below                                         |
| MERGE   | 40    | G7 to G9; form to lemma page; self-loop; inline   |
|         |       | modifiers; decoding; diacritic alias; undeclared  |
|         |       | id; skipped dump lines; page title rule; strip    |
|         |       | rule parsing                                      |
| CUT     | 1     | `test_reads_an_edge_file_with_sorted_spaced_keys` |
| MOVE    | 1     | `test_filter_writes_compact_utf8_lines`           |

KEEP:

- `test_edges.py`: `test_root_yields_one_edge_per_listed_root`,
  `test_etymon_chain_survives_a_term_less_head`,
  `test_etymon_skips_stringified_template_copy`
- `test_inline.py::test_chain_below_a_dash_placeholder_is_kept`
- `test_wiktextract.py::test_field_paths_list_every_field_the_struct_reads`
- `test_merge.py::test_alias_folded_same_term_edge_is_dropped_and_logged`
- `test_cli.py::test_load_reports_merged_edges_against_staged_edges`
- `test_edgefile.py::test_writes_compact_utf8_lines`
- `test_web_role.py`: all three. A reload swaps in a fresh `public`, so
  the grants and the role's timeout must be checked on the new
  generation.

Seventeen tests from `f39d600` are gone. Two were CUTs and two were the
entry validation MERGE group, which went with pydantic;
`test_stream_skips_an_entry_naming_no_word` now covers that ground.
The `project_entry` tests became the decoding group. The rest were KEEP
tests that later commits replaced.
