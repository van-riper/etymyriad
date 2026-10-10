# Etymyriad

Etymyriad shows where words come from. Pick a word and it draws a family tree
of its ancestors and descendants, backed by a sourced, citable dataset.

> _etymology + myriad_: a myriad of word origins.

## Status

The Indo-European part of Wiktionary is loaded and browsable at
`/tree/[lang]/[headword]`, which draws a bounded family tree around one
word.

## Architecture

[`docs/DESIGN.md`](docs/DESIGN.md) covers the architecture, the data model,
and the reasoning behind them.

## Development

Prerequisites: Node 22+, uv, podman (or docker), git.

```sh
# 1. Start local Postgres, create the role/database (one-time), apply schema
make db-up
make db-init
make db-apply

# 2. ETL (Python 3.13, managed by uv)
cd etl && uv sync

# 3. Web app (frontend + API)
cd web && npm install && npm run dev
```

See the `Makefile` for all targets.

Undoing a bad local load doesn't need a full ETL reload: `make
db-snapshot` saves a known-good local DB to `db/snapshot.dump`, and
`make db-restore` restores it in minutes. See `CLAUDE.md`'s Local-dev
gotchas for that and the Neon-side equivalent (point-in-time restore).

### Bumping the version

Edit the `version` key in both `etl/pyproject.toml` and
`web/package.json`, then run:

```sh
make etl-sync && make web-install
```

This refreshes `etl/uv.lock` and `web/package-lock.json` to match.

## Licensing

etymyriad carries two licenses: one for the code, one for the data.

- **Source code** (`etl/`, `web/`, `db/`): **MIT**, see [`LICENSE`](LICENSE).
- **Derived etymology dataset**: **CC BY-SA 4.0**, inherited from its sources.
  (see below)

### Data sources and attribution

The dataset is built from:

- **Wiktionary**: the underlying lexical and etymological content,
  dual-licensed under
  [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/) and the GFDL.
- **Wiktextract / kaikki.org** (Tatu Ylönen): a machine-readable extraction of
  Wiktionary, distributed under the same terms.
- **Etymological Wordnet** (Gerard de Melo): used only to validate the parser,
  derived from Wiktionary, CC BY-SA 3.0.

Because the dataset is a derivative of Wiktionary, any redistribution of the
data (a database dump, an export endpoint) must:

1. **Attribute** Wiktionary and its contributors.
2. **Share alike**: license the redistributed data under CC BY-SA 4.0.
3. **Indicate changes** made during normalization.

The interactive site satisfies attribution by linking each etymological edge
back to its Wiktionary source page. Provenance is stored per edge in the
`etymology.source_ref` column.

### UI theme

The site's light/dark color palette is
[Flexoki](https://github.com/kepano/flexoki) by Steph Ango.
