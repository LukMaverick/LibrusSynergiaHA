"""Testy rejestracji karty Lovelace (karta.py) z atrapami HA."""

import asyncio
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

import _ha_stub
from _pure import load_full

pytestmark = pytest.mark.skipif(
    not _ha_stub.STUBBED, reason="testy z atrapami HA; prawdziwy HA ma wlasne testy"
)

karta = load_full("karta") if _ha_stub.STUBBED else None
const = load_full("const") if _ha_stub.STUBBED else None

URL = f"{karta.CARD_URL}?v={const.VERSION}" if karta else ""


def _hass(lovelace):
    hass = MagicMock()
    hass.data = {"lovelace": lovelace} if lovelace is not None else {}
    return hass


def _zasoby(items, loaded=True):
    return SimpleNamespace(
        loaded=loaded,
        async_items=lambda: items,
        async_create_item=AsyncMock(),
        async_update_item=AsyncMock(),
        async_load=AsyncMock(),
    )


def test_tworzy_zasob_gdy_brak():
    z = _zasoby([])
    hass = _hass(SimpleNamespace(mode="storage", resources=z))
    assert asyncio.run(karta._async_ensure_resource(hass, URL)) is True
    z.async_create_item.assert_awaited_once_with({"res_type": "module", "url": URL})


def test_aktualizuje_wersje_zamiast_dodawac_duplikat():
    z = _zasoby([{"id": "abc", "url": f"{karta.CARD_URL}?v=1.0.0", "type": "module"}])
    hass = _hass(SimpleNamespace(mode="storage", resources=z))
    assert asyncio.run(karta._async_ensure_resource(hass, URL)) is True
    z.async_create_item.assert_not_awaited()
    z.async_update_item.assert_awaited_once_with("abc", {"res_type": "module", "url": URL})


def test_nic_nie_robi_gdy_zasob_aktualny():
    z = _zasoby([{"id": "abc", "url": URL}])
    hass = _hass(SimpleNamespace(mode="storage", resources=z))
    assert asyncio.run(karta._async_ensure_resource(hass, URL)) is True
    z.async_create_item.assert_not_awaited()
    z.async_update_item.assert_not_awaited()


def test_wczytuje_zasoby_jesli_jeszcze_nie_zaladowane():
    z = _zasoby([], loaded=False)
    hass = _hass(SimpleNamespace(mode="storage", resources=z))
    asyncio.run(karta._async_ensure_resource(hass, URL))
    z.async_load.assert_awaited_once()


def test_tryb_yaml_brak_lovelace_i_slownikowy_format():
    assert asyncio.run(karta._async_ensure_resource(_hass(None), URL)) is False
    assert asyncio.run(karta._async_ensure_resource(
        _hass(SimpleNamespace(mode="yaml", resources=_zasoby([]))), URL)) is False
    # starsze HA: slownik; kolekcja YAML nie ma async_create_item
    yaml_kolekcja = SimpleNamespace(loaded=True, async_items=lambda: [])
    assert asyncio.run(karta._async_ensure_resource(
        _hass({"mode": "storage", "resources": yaml_kolekcja}), URL)) is False
    z = _zasoby([])
    assert asyncio.run(karta._async_ensure_resource(
        _hass({"mode": "storage", "resources": z}), URL)) is True


def test_rejestracja_fallback_przez_add_extra_js_url(monkeypatch):
    hass = _hass(None)
    hass.data = {}
    hass.http.async_register_static_paths = AsyncMock()
    dodano = MagicMock()
    import sys
    sys.modules["homeassistant.components.frontend"].add_extra_js_url = dodano
    asyncio.run(karta.async_register_frontend(hass))
    hass.http.async_register_static_paths.assert_awaited_once()
    dodano.assert_called_once_with(hass, URL)
    # drugie wywolanie nic nie robi
    asyncio.run(karta.async_register_frontend(hass))
    hass.http.async_register_static_paths.assert_awaited_once()


def test_wersja_zgodna_z_manifestem_i_plik_karty_istnieje():
    sciezka = Path(__file__).parent.parent / "custom_components" / "librus_apix"
    manifest = json.loads((sciezka / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["version"] == const.VERSION
    assert (sciezka / "frontend" / karta.CARD_FILE).exists()
    assert "http" in manifest["dependencies"]
    assert "lovelace" in manifest["after_dependencies"]
