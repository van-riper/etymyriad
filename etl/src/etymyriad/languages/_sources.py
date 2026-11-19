"""Fetch Wiktionary's language data and Wikidata's ISO 639 codes."""

import json
import unicodedata
from collections import defaultdict
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from etymyriad.config import WIKIDATA_SPARQL_URL, WIKTIONARY_API_URL
from etymyriad.languages._registry import Registry
from etymyriad.languages._snapshot import (
    WikidataIso,
    WiktionaryExports,
    build_snapshot,
    strip_modules,
)

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence
    from pathlib import Path

    import httpx

    from etymyriad.languages._snapshot import Snapshot

# Asking export_languages for every key fails Lua serialisation, so ask
# only for the fields the snapshot reads.
_LANGUAGE_KEYS = (
    "1",
    "2",
    "3",
    "4",
    "type",
    "wikimedia_codes",
    "strip_diacritics",
)
_SCRIPT_KEYS = ("ranges", "strip_diacritics")
# Combining Diacritical Marks, which every script borrows.
_SHARED_MARKS = tuple(map(chr, range(0x0300, 0x0370)))
# wdt: reads best-rank statements only, which drops deprecated codes.
_ISO_QUERY = """
SELECT ?item ?property ?code WHERE {
  VALUES ?property { wdt:P218 wdt:P219 wdt:P220 wdt:P1798 }
  ?item ?property ?code .
}
"""


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
    """
    arguments = ["", *keys] if keys else []
    invoke = "|".join(["{{#invoke:JSON data", function, *arguments]) + "}}"
    return json.loads(_expand_templates(client, invoke))


def _expand_templates(client: httpx.Client, text: str) -> str:
    """Expand wikitext through the MediaWiki API.

    Returns:
        The expanded wikitext.

    Raises:
        WiktionaryExportError: If a module reported a Lua error.
    """
    response = client.post(
        WIKTIONARY_API_URL,
        data={
            "action": "expandtemplates",
            "prop": "wikitext",
            "format": "json",
            "text": text,
        },
    )
    response.raise_for_status()
    wikitext = response.json()["expandtemplates"]["wikitext"]
    if "scribunto-error" in wikitext:
        raise WiktionaryExportError(wikitext)
    return wikitext


def _probe(ranges: Sequence[int]) -> tuple[str, list[str]]:
    """Pick a script's first bare letter and every mark it could carry.

    Args:
        ranges: The script's code point ranges, as flat low/high pairs.

    Returns:
        The letter, and the combining marks in code point order. A mark
        that decomposes is left out, since NFD text never holds it.
    """
    characters = [
        chr(code_point)
        for low, high in zip(ranges[::2], ranges[1::2], strict=True)
        for code_point in range(low, high + 1)
    ]
    base = next(
        character
        for character in characters
        if unicodedata.category(character) in {"Ll", "Lo"}
        and not unicodedata.decomposition(character)
    )
    marks = sorted({
        character
        for character in (*characters, *_SHARED_MARKS)
        if unicodedata.category(character).startswith("M")
        and unicodedata.normalize("NFD", character) == character
    })
    return base, marks


def fetch_module_marks(
    client: httpx.Client, wiktionary: WiktionaryExports
) -> dict[str, str]:
    """Find the marks each language's Lua strip modules drop.

    Wiktionary strips a language's diacritics with its own function,
    so every quirk a module has for one language shows in the probe:
    one bare letter per candidate mark, each a separate word.

    Args:
        client: HTTP client to send the request with.
        wiktionary: The exports naming each module and script.

    Returns:
        The dropped marks per language code, for languages with one.

    Raises:
        WiktionaryExportError: If a module reported a Lua error, or a
            probe came back with a different number of words.
    """
    probes = [
        (code, script, *_probe(wiktionary.scripts[script]["ranges"]))
        for code, raw in wiktionary.languages.items()
        for script in strip_modules(raw, wiktionary.scripts)
    ]
    if not probes:
        return {}

    invokes = "\n".join(
        "{{#invoke:languages/templates|getByCode|"
        f"{code}|stripDiacritics|{' '.join(base + mark for mark in marks)}"
        f"|{script}}}}}"
        for code, script, base, marks in probes
    )
    replies = _expand_templates(client, invokes).split("\n")

    module_marks: dict[str, str] = {}
    for (code, script, base, marks), reply in zip(probes, replies, strict=True):
        words = reply.split(" ")
        if len(words) != len(marks):
            message = f"{code} {script} probe lost words: {reply!r}"
            raise WiktionaryExportError(message)
        dropped = (
            mark
            for mark, word in zip(marks, words, strict=True)
            if word == base
        )
        module_marks[code] = module_marks.get(code, "") + "".join(dropped)
    return module_marks


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
        WIKIDATA_SPARQL_URL,
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
    iso639_5_codes = frozenset().union(*by_property["P1798"].values())
    return WikidataIso(
        iso639_3_by_item=_frozen(by_property["P220"]),
        iso639_1_by_item=_frozen(by_property["P218"]),
        iso639_2_by_item=_frozen(by_property["P219"]),
        iso639_5_codes=iso639_5_codes,
    )


def sync_snapshot(output: Path, client: httpx.Client) -> Snapshot:
    """Fetch every source, join them, and write the snapshot to `output`.

    Nothing is written unless every fetch succeeds and the joined
    snapshot links into a Registry, so a failed sync leaves the
    committed snapshot as it was. A broken join raises whatever the
    linking raises (KeyError for a missing family, ValueError for a
    cycle or an unknown type).

    Returns:
        The snapshot written.
    """
    wiktionary = WiktionaryExports(
        languages=fetch_json_data(client, "export_languages", _LANGUAGE_KEYS),
        families=fetch_json_data(client, "export_families"),
        varieties=fetch_json_data(client, "export_etymology_languages"),
        scripts=fetch_json_data(client, "export_scripts", _SCRIPT_KEYS),
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
        fetch_module_marks(client, wiktionary),
    )
    Registry(snapshot)

    output.parent.mkdir(parents=True, exist_ok=True)
    # Write beside the target, then swap, so an interrupted write never
    # truncates the committed snapshot.
    staged = output.with_name(f"{output.name}.tmp")
    staged.write_text(
        json.dumps(snapshot, ensure_ascii=False, indent=1, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )
    staged.replace(output)
    return snapshot
