"""Testy rejestracji kart Lovelace (karta.py) z atrapami HA."""

import asyncio
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

PLIK = "librus-terminarz-card.js"
URL = f"{karta.URL_BASE}/{PLIK}?v={const.VERSION}" if karta else ""


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
    assert asyncio.run(karta._async_ensure_resource(hass, PLIK, URL)) is True
    z.async_create_item.assert_awaited_once_with({"res_type": "module", "url": URL})


def test_aktualizuje_wersje_zamiast_dodawac_duplikat():
    z = _zasoby([{"id": "abc", "url": f"{karta.URL_BASE}/{PLIK}?v=0.0.1", "type": "module"}])
    hass = _hass(SimpleNamespace(mode="storage", resources=z))
    assert asyncio.run(karta._async_ensure_resource(hass, PLIK, URL)) is True
    z.async_update_item.assert_awaited_once_with("abc", {"res_type": "module", "url": URL})
    z.async_create_item.assert_not_awaited()


def test_nie_rusza_aktualnego_zasobu():
    z = _zasoby([{"id": "abc", "url": URL}])
    hass = _hass(SimpleNamespace(mode="storage", resources=z))
    assert asyncio.run(karta._async_ensure_resource(hass, PLIK, URL)) is True
    z.async_update_item.assert_not_awaited()
    z.async_create_item.assert_not_awaited()


def test_tryb_yaml_i_brak_lovelace():
    z = _zasoby([])
    assert asyncio.run(karta._async_ensure_resource(_hass(SimpleNamespace(mode="yaml", resources=z)), PLIK, URL)) is False
    assert asyncio.run(karta._async_ensure_resource(_hass(None), PLIK, URL)) is False


def test_slownik_lovelace():
    z = _zasoby([])
    hass = _hass({"mode": "storage", "resources": z})
    assert asyncio.run(karta._async_ensure_resource(hass, PLIK, URL)) is True


def test_rejestracja_raz_i_fallback_yaml():
    hass = _hass(SimpleNamespace(mode="yaml", resources=_zasoby([])))
    hass.http.async_register_static_paths = AsyncMock()
    frontend = __import__("sys").modules["homeassistant.components.frontend"]
    frontend.add_extra_js_url = MagicMock()
    asyncio.run(karta.async_register_frontend(hass))
    asyncio.run(karta.async_register_frontend(hass))  # drugie wywolanie nic nie robi
    hass.http.async_register_static_paths.assert_awaited_once()
    frontend.add_extra_js_url.assert_called_once_with(hass, URL)
