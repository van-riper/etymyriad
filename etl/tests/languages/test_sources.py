"""Tests for fetching Wiktionary and Wikidata language data."""

import json
from typing import TYPE_CHECKING
from urllib.parse import parse_qs

import httpx
import pytest

from etymyriad.languages._snapshot import WiktionaryExports
from etymyriad.languages._sources import (
    WiktionaryExportError,
    fetch_json_data,
    fetch_module_marks,
    fetch_wikidata_iso,
    sync_snapshot,
)

if TYPE_CHECKING:
    from pathlib import Path

_LUA_ERROR = (
    '<strong class="error"><span class="scribunto-error">Lua error in '
    "Module:JSON_data: serialisation failed</span></strong>"
)


_FATHA = "\u064e"
_ARABIC = WiktionaryExports(
    languages={
        "ar": {"4": "Arab", "strip_diacritics": {"Arab": "ar-stripdiacritics"}},
        "en": {"4": "Latn"},
    },
    families={},
    varieties={},
    scripts={
        "Arab": {"ranges": [0x0628, 0x0628, 0x064E, 0x064F]},
        "Latn": {"ranges": [0x0061, 0x007A]},
    },
)


def _request_text(request: httpx.Request) -> str:
    return parse_qs(request.content.decode())["text"][0]


def _expand_response(wikitext: str) -> httpx.Response:
    return httpx.Response(200, json={"expandtemplates": {"wikitext": wikitext}})


def _sparql_response(rows: list[tuple[int, str, str]]) -> httpx.Response:
    bindings = [
        {
            "item": {"value": f"http://www.wikidata.org/entity/Q{item}"},
            "property": {
                "value": f"http://www.wikidata.org/prop/direct/{prop}"
            },
            "code": {"value": code},
        }
        for item, prop, code in rows
    ]
    return httpx.Response(200, json={"results": {"bindings": bindings}})


def test_fetch_json_data_requests_keys_and_parses_wikitext() -> None:
    """The invoke text carries the empty type filter, then the keys."""
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(_request_text(request))
        return _expand_response('{"en": {"1": "English"}}')

    client = httpx.Client(transport=httpx.MockTransport(handler))
    records = fetch_json_data(client, "export_languages", ("1", "type"))
    assert records == {"en": {"1": "English"}}
    assert seen == ["{{#invoke:JSON data|export_languages||1|type}}"]


def test_fetch_json_data_raises_on_lua_error() -> None:
    """A Lua failure arrives as HTTP 200 wikitext and must not parse."""
    client = httpx.Client(
        transport=httpx.MockTransport(lambda _: _expand_response(_LUA_ERROR))
    )
    with pytest.raises(WiktionaryExportError, match="Lua error"):
        fetch_json_data(client, "export_languages")


def test_fetch_wikidata_iso_groups_codes_by_property() -> None:
    """Each property's values land in their own per-item map."""
    response = _sparql_response([
        (1860, "P220", "eng"),
        (1860, "P218", "en"),
        (150, "P219", "fre"),
        (150, "P219", "fra"),
        (26721, "P1798", "gmw"),
    ])
    client = httpx.Client(transport=httpx.MockTransport(lambda _: response))
    iso = fetch_wikidata_iso(client)
    assert iso.iso639_3_by_item == {1860: frozenset({"eng"})}
    assert iso.iso639_1_by_item == {1860: frozenset({"en"})}
    assert iso.iso639_2_by_item == {150: frozenset({"fre", "fra"})}
    assert iso.iso639_5_codes == frozenset({"gmw"})


def test_fetch_wikidata_iso_rejects_html_error_page() -> None:
    """Wikidata's rate-limit page is HTML, so the JSON parse must fail."""
    html = httpx.Response(200, text="<!DOCTYPE html><title>Wikimedia Error")
    client = httpx.Client(transport=httpx.MockTransport(lambda _: html))
    with pytest.raises(ValueError, match="Expecting value"):
        fetch_wikidata_iso(client)


def test_sync_snapshot_leaves_file_untouched_on_failure(
    tmp_path: Path,
) -> None:
    """A failed fetch never overwrites the committed snapshot."""
    output = tmp_path / "registry.json"
    output.write_text('{"old": true}', encoding="utf-8")
    client = httpx.Client(
        transport=httpx.MockTransport(lambda _: _expand_response(_LUA_ERROR))
    )
    with pytest.raises(WiktionaryExportError):
        sync_snapshot(output, client)
    assert json.loads(output.read_text(encoding="utf-8")) == {"old": True}


def test_sync_snapshot_writes_joined_snapshot(tmp_path: Path) -> None:
    """A full sync fetches four sources and writes one snapshot."""

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "query.wikidata.org":
            return _sparql_response([(1860, "P218", "en")])
        text = _request_text(request)
        if "export_languages" in text:
            return _expand_response(
                '{"en": {"1": "English", "2": 1860, "type": "regular"}}'
            )
        return _expand_response("{}")

    output = tmp_path / "registry.json"
    sync_snapshot(output, httpx.Client(transport=httpx.MockTransport(handler)))
    snapshot = json.loads(output.read_text(encoding="utf-8"))
    assert snapshot["languages"]["en"]["iso639_1"] == "en"
    assert "wiktionary" in snapshot["sources"]


def test_sync_snapshot_refuses_a_snapshot_the_registry_cannot_link(
    tmp_path: Path,
) -> None:
    """A language pointing at a missing family must not reach disk."""

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "query.wikidata.org":
            return _sparql_response([])
        if "export_languages" in _request_text(request):
            return _expand_response(
                '{"en": {"1": "English", "3": "gmw", "type": "regular"}}'
            )
        return _expand_response("{}")

    output = tmp_path / "registry.json"
    output.write_text('{"old": true}', encoding="utf-8")
    client = httpx.Client(transport=httpx.MockTransport(handler))
    with pytest.raises(KeyError, match="gmw"):
        sync_snapshot(output, client)
    assert json.loads(output.read_text(encoding="utf-8")) == {"old": True}
    assert [path.name for path in tmp_path.iterdir()] == ["registry.json"]


def test_fetch_module_marks_keeps_the_marks_a_module_drops() -> None:
    """Arabic's module drops fatha after the bare letter and keeps damma."""
    seen: list[str] = []

    def strip_fatha(request: httpx.Request) -> httpx.Response:
        text = _request_text(request)
        seen.append(text)
        probe = text.split("|")[4]
        return _expand_response(probe.replace(_FATHA, ""))

    client = httpx.Client(transport=httpx.MockTransport(strip_fatha))
    assert fetch_module_marks(client, _ARABIC) == {"ar": _FATHA}
    assert seen[0].startswith(
        "{{#invoke:languages/templates|getByCode|ar|stripDiacritics|"
        "\u0628\u0300 \u0628\u0301"
    )
    assert seen[0].endswith(f"\u0628{_FATHA} \u0628\u064f|Arab}}}}")


def test_fetch_module_marks_rejects_a_reply_that_lost_words() -> None:
    """A module that merges words would pair marks with the wrong word."""
    client = httpx.Client(
        transport=httpx.MockTransport(lambda _: _expand_response("\u0628"))
    )
    with pytest.raises(WiktionaryExportError, match="ar"):
        fetch_module_marks(client, _ARABIC)


def test_fetch_module_marks_skips_the_request_with_nothing_to_probe() -> None:
    """Without a Lua strip module there is nothing to ask Wiktionary."""
    exports = _ARABIC._replace(languages={"en": {"4": "Latn"}})
    client = httpx.Client(
        transport=httpx.MockTransport(lambda _: pytest.fail("sent a request"))
    )
    assert fetch_module_marks(client, exports) == {}
