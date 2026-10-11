"""Rejestracja kart Lovelace dostarczanych razem z integracja."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Optional

from homeassistant.core import HomeAssistant

from .const import DOMAIN, VERSION

_LOGGER = logging.getLogger(__name__)

URL_BASE = "/librus_apix_static"
# Po polaczeniu z galezia planu zajec: ("librus-card.js", "librus-terminarz-card.js")
KARTY = ("librus-terminarz-card.js",)
CARD_URL = f"{URL_BASE}/{KARTY[0]}"
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


async def _async_ensure_resource(hass: HomeAssistant, plik: str, url: str) -> bool:
    """Dodaj lub zaktualizuj zasob Lovelace (tylko tryb storage). Zwraca True gdy sie udalo."""
    resources, mode = _lovelace_resources(hass)
    if resources is None or mode == "yaml":
        return False
    if not hasattr(resources, "async_create_item"):
        return False  # kolekcja YAML - nie da sie edytowac

    if not getattr(resources, "loaded", True):
        await resources.async_load()
        resources.loaded = True

    bazowy = f"{URL_BASE}/{plik}"
    for item in resources.async_items():
        if str(item.get("url", "")).split("?")[0] == bazowy:
            if item.get("url") != url:
                await resources.async_update_item(item["id"], {"res_type": "module", "url": url})
            return True
    await resources.async_create_item({"res_type": "module", "url": url})
    return True


async def async_register_frontend(hass: HomeAssistant) -> None:
    """Udostepnij pliki kart i zarejestruj je jako zasoby (raz dla calego HA)."""
    dane = hass.data.setdefault(DOMAIN, {})
    if dane.get(_REGISTERED_KEY):
        return

    from homeassistant.components.http import StaticPathConfig

    sciezka = Path(__file__).parent / "frontend"
    await hass.http.async_register_static_paths(
        [StaticPathConfig(URL_BASE, str(sciezka), cache_headers=False)]
    )
    dane[_REGISTERED_KEY] = True

    for plik in KARTY:
        bazowy = f"{URL_BASE}/{plik}"
        url = f"{bazowy}?v={VERSION}"
        try:
            zarejestrowano = await _async_ensure_resource(hass, plik, url)
        except Exception as err:  # noqa: BLE001 - wewnetrzne API Lovelace bywa zmieniane
            _LOGGER.warning("Nie udalo sie dodac zasobu Lovelace %s automatycznie: %s", plik, err)
            zarejestrowano = False

        if not zarejestrowano:
            # Tryb YAML albo zmienione API: zaladuj karte globalnie (bez zasobu, zeby nie ladowac dwa razy)
            from homeassistant.components.frontend import add_extra_js_url

            add_extra_js_url(hass, url)
            _LOGGER.info(
                "Karta %s ladowana przez add_extra_js_url. W trybie YAML mozesz zamiast tego "
                "dodac zasob: url: %s, type: module",
                plik,
                bazowy,
            )
