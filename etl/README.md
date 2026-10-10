# etymyriad (etl)

The offline ETL that turns Wiktextract data into the etymology graph.

```mermaid
flowchart LR
    parse["parse<br/>(stream JSONL)"] --> normalize["normalize<br/>(raw entries → graph model)"] --> load["load<br/>(build a fresh schema, then swap it live)"]
```

## Usage

```sh
uv sync  # install (fetches Python 3.13)
# DATABASE_URL/WIKTEXTRACT_DUMP/WIKTEXTRACT_DUMP_DATE all default to
# the standard local dev DB and acquired-dump path (see config.py).

# Once per dump: kaikki.org only distributes one combined dump (every language
# mixed together). Filter it down to Indo-European first:
uv run etymyriad filter-ine --input raw-wiktextract-data.jsonl.gz \
                             --output ../data/raw/indo-european.jsonl

uv run etymyriad --help     # every command and its options
uv run pytest               # tests
```
