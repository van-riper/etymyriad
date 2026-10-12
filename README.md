# Etymyriad

Etymyriad shows where words come from. Pick a word and it draws a family tree of
its ancestors and descendants, backed by a sourced, citable dataset.

> _etymology + myriad_: a myriad of word origins.

## Status

The Indo-European part of Wiktionary is loaded and browsable at
`/tree/[lang]/[headword]`, which draws a bounded family tree around one word.

## Architecture

[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) covers the architecture, the data
model, and the reasoning behind them. [`docs/DESIGN.md`](docs/DESIGN.md)
describes the UI's visual design.

## Development

Prerequisites: Node 22+, uv, git, and a native Postgres server (see the local
Postgres notes in `CLAUDE.md`).

```sh
# 1. Start local Postgres, create the role/database (one-time), apply schema
make db-up
make db-init
make db-apply

# 2. ETL (Python 3.13, managed by uv)
cd etl && uv sync
uv run etymyriad all

# 3. Web app (frontend + API)
cd web && npm install && npm run dev
```

`make help` lists every target, including `db-snapshot` and `db-restore` for
rewinding a bad local load without a full ETL reload.

## Licensing

etymyriad carries two licenses: one for the code, one for the data.

- **Source code** (`etl/`, `web/`, `db/`): **MIT**, see [`LICENSE`](LICENSE).
- **Derived etymology dataset**: **CC BY-SA 4.0**, inherited from its sources.
  (see below)

### Data sources and attribution

The dataset is built from:

- **Wiktionary**: the underlying lexical and etymological content, dual-licensed
  under [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/) and the
  GFDL.
- **Wiktextract / kaikki.org** (Tatu Ylönen): a machine-readable extraction of
  Wiktionary, distributed under the same terms.

Because the dataset is a derivative of Wiktionary, any redistribution of the
data (a database dump, an export endpoint) must:

1. **Attribute** Wiktionary and its contributors.
2. **Share alike**: license the redistributed data under CC BY-SA 4.0.
3. **Indicate changes** made during normalization.

On the site, each word's detail card links to its Wiktionary page. Every edge
stores its Wiktionary origin in the `edge.anchor` column, and the `source_ref()`
function turns it into a full citation.

### UI theme

The site's light/dark color palette is
[Flexoki](https://github.com/kepano/flexoki) by Steph Ango.
