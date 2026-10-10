"""Fetch Wiktionary's language data and Wikidata's ISO 639 codes."""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from etymyriad.languages._snapshot import (
    WikidataIso,
    WiktionaryExports,
    build_snapshot,
)

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence
    from pathlib import Path

    import httpx

    from etymyriad.languages._snapshot import Snapshot

USER_AGENT = "etymyriad-etl (https://etymyriad.com)"
_WIKTIONARY_API = "https://en.wiktionary.org/w/api.php"
_WIKIDATA_SPARQL = "https://query.wikidata.org/sparql"
# Asking export_languages for every key fails Lua serialisation, so ask
# only for the positional fields the snapshot reads.
_LANGUAGE_KEYS = ("1", "2", "3", "4", "type", "wikimedia_codes")
# wdt: reads best-rank statements only, which drops deprecated codes.
_ISO_QUERY = """
SELECT ?item ?property ?code WHERE {
  VALUES ?property { wdt:P218 wdt:P219 wdt:P220 wdt:P1798 }
  ?item ?property ?code .
}
"""
_ISO639_5_PROPERTY = "P1798"


class WiktionaryExportError(RuntimeError):
    """Module:JSON data answered with a Lua error instead of JSON."""


def fetch_json_data(
    client: httpx.Client, function: str, keys: Sequence[str] = ()
) -> dict[str, Any]:
    """Expand one Module:JSON data export through the MediaWiki API.

    Args:
        client: HTTP client to send the request with.
        function: Export name, e.g. "export_families".
        keys: Record keys to export. The empty slot before them is the
            module's language-type filter, which it documents as broken.

    Returns:
        The export's records, keyed by Wiktionary code.

    Raises:
        WiktionaryExportError: If the module reported a Lua error.
    """
    arguments = ["", *keys] if keys else []
    invoke = "|".join(["{{#invoke:JSON data", function, *arguments]) + "}}"
    response = client.get(
        _WIKTIONARY_API,
        params={
            "action": "expandtemplates",
            "prop": "wikitext",
            "format": "json",
            "text": invoke,
        },
    )
    response.raise_for_status()
    wikitext = response.json()["expandtemplates"]["wikitext"]
    if "scribunto-error" in wikitext:
        raise WiktionaryExportError(wikitext)
    return json.loads(wikitext)


def _item_number(uri: str) -> int:
    return int(uri.rsplit("Q", 1)[1])


def _frozen(
    by_item: Mapping[int, set[str]],
) -> dict[int, frozenset[str]]:
    return {item: frozenset(codes) for item, codes in by_item.items()}


def fetch_wikidata_iso(client: httpx.Client) -> WikidataIso:
    """Fetch every ISO 639-1, -2, -3, and -5 code Wikidata states.

    A non-JSON body, such as an HTML rate-limit page served with HTTP
    200, raises ValueError from the JSON parse.

    Returns:
        The codes, grouped by property and Wikidata item.
    """
    response = client.post(
        _WIKIDATA_SPARQL,
        data={"query": _ISO_QUERY},
        headers={"Accept": "application/sparql-results+json"},
    )
    response.raise_for_status()
    by_property: defaultdict[str, defaultdict[int, set[str]]] = defaultdict(
        lambda: defaultdict(set)
    )
    for row in response.json()["results"]["bindings"]:
        prop = row["property"]["value"].rsplit("/", 1)[1]
        item = _item_number(row["item"]["value"])
        by_property[prop][item].add(row["code"]["value"])
    iso639_5_codes = frozenset().union(
        *by_property[_ISO639_5_PROPERTY].values()
    )
    return WikidataIso(
        iso639_3_by_item=_frozen(by_property["P220"]),
        iso639_1_by_item=_frozen(by_property["P218"]),
        iso639_2_by_item=_frozen(by_property["P219"]),
        iso639_5_codes=iso639_5_codes,
    )


def sync_snapshot(output: Path, client: httpx.Client) -> Snapshot:
    """Fetch every source, join them, and write the snapshot to `output`.

    Nothing is written unless every fetch and the join succeed, so a
    failed sync leaves the committed snapshot as it was.

    Returns:
        The snapshot written.
    """
    wiktionary = WiktionaryExports(
        languages=fetch_json_data(client, "export_languages", _LANGUAGE_KEYS),
        families=fetch_json_data(client, "export_families"),
        varieties=fetch_json_data(client, "export_etymology_languages"),
    )
    fetched_on = datetime.now(UTC).date().isoformat()
    snapshot = build_snapshot(
        wiktionary,
        fetch_wikidata_iso(client),
        {
            "wiktionary": (
                "en.wiktionary.org Module:JSON data, CC BY-SA 4.0, "
                f"fetched {fetched_on}"
            ),
            "wikidata": f"query.wikidata.org, CC0, fetched {fetched_on}",
        },
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(snapshot, ensure_ascii=False, indent=1, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )
    return snapshot
