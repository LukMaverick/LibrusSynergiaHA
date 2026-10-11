"""Rejestracja karty Lovelace librus-card dostarczanej razem z integracja."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Optional

from homeassistant.core import HomeAssistant

from .const import DOMAIN, VERSION

_LOGGER = logging.getLogger(__name__)

URL_BASE = "/librus_apix_static"
CARD_FILE = "librus-card.js"
CARD_URL = f"{URL_BASE}/{CARD_FILE}"
_REGISTERED_KEY = "_frontend_registered"


def _lovelace_resources(hass: HomeAssistant) -> tuple[Optional[Any], Optional[str]]:
    """Zwroc (kolekcja zasobow, tryb) niezaleznie od wersji HA (obiekt albo slownik)."""
    lovelace = hass.data.get("lovelace")
    if lovelace is None:
        return None, None
    if isinstance(lovelace, dict):
        return lovelace.get("resources"), lovelace.get("mode")
    mode = getattr(lovelace, "mode", None) or getattr(lovelace, "resource_mode", None)
    return getattr(lovelace, "resources", None), mode


async def _async_ensure_resource(hass: HomeAssistant, url: str) -> bool:
    """Dodaj lub zaktualizuj zasob Lovelace (tylko tryb storage). Zwraca True gdy sie udalo."""
    resources, mode = _lovelace_resources(hass)
    if resources is None or mode == "yaml":
        return False
    if not hasattr(resources, "async_create_item"):
        return False  # kolekcja YAML - nie da sie edytowac

    if not getattr(resources, "loaded", True):
        await resources.async_load()
        resources.loaded = True

    for item in resources.async_items():
        if str(item.get("url", "")).split("?")[0] == CARD_URL:
            if item.get("url") != url:
                await resources.async_update_item(item["id"], {"res_type": "module", "url": url})
            return True
    await resources.async_create_item({"res_type": "module", "url": url})
    return True


async def async_register_frontend(hass: HomeAssistant) -> None:
    """Udostepnij plik karty i zarejestruj go jako zasob (raz dla calego HA)."""
    dane = hass.data.setdefault(DOMAIN, {})
    if dane.get(_REGISTERED_KEY):
        return

    from homeassistant.components.http import StaticPathConfig

    sciezka = Path(__file__).parent / "frontend"
    await hass.http.async_register_static_paths(
        [StaticPathConfig(URL_BASE, str(sciezka), cache_headers=False)]
    )
    dane[_REGISTERED_KEY] = True

    url = f"{CARD_URL}?v={VERSION}"
    try:
        zarejestrowano = await _async_ensure_resource(hass, url)
    except Exception as err:  # noqa: BLE001 - wewnetrzne API Lovelace bywa zmieniane
        _LOGGER.warning("Nie udalo sie dodac zasobu Lovelace automatycznie: %s", err)
        zarejestrowano = False

    if not zarejestrowano:
        # Tryb YAML albo zmienione API: zaladuj karte globalnie (bez zasobu, zeby nie ladowac dwa razy)
        from homeassistant.components.frontend import add_extra_js_url

        add_extra_js_url(hass, url)
        _LOGGER.info(
            "Karta librus-card ladowana przez add_extra_js_url. W trybie YAML mozesz zamiast tego "
            "dodac zasob: url: %s, type: module",
            CARD_URL,
        )
