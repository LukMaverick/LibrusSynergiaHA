"""Przyciski testowe: wyslij testowy SMS/push tak jak przy prawdziwej nowej ocenie/uwadze."""

import logging
from typing import Any, Dict

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_PUSH_NOTIFY, CONF_SMS_ENABLED, DOMAIN, TYP_OCENA, TYP_UWAGA
from .coordinator import LibrusDataUpdateCoordinator
from .sensor import _device_info
from .sms import async_powiadom, dane_testowe, podziel_adresy, podziel_uslugi_notify

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Dodaj przyciski testowe dla wpisu."""
    coordinator: LibrusDataUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]["coordinator"]
    async_add_entities(
        [
            LibrusTestPowiadomieniaButton(coordinator, config_entry, TYP_OCENA),
            LibrusTestPowiadomieniaButton(coordinator, config_entry, TYP_UWAGA),
        ]
    )


class LibrusTestPowiadomieniaButton(CoordinatorEntity, ButtonEntity):
    """Przycisk: wyslij testowe powiadomienie (SMS przez bramke + push) dla ocen lub uwag."""

    def __init__(self, coordinator: LibrusDataUpdateCoordinator, config_entry: ConfigEntry, typ: str) -> None:
        super().__init__(coordinator)
        self._config_entry = config_entry
        self._typ = typ
        self._attr_has_entity_name = False
        self._attr_name = "Test powiadomien - ocena" if typ == TYP_OCENA else "Test powiadomien - uwaga"
        self._attr_unique_id = f"{config_entry.entry_id}_test_powiadomien_{typ}"
        self._attr_icon = "mdi:message-flash-outline" if typ == TYP_OCENA else "mdi:comment-flash-outline"

    @property
    def device_info(self) -> Dict[str, Any]:
        return _device_info(self.coordinator, self._config_entry)

    def _dane_testowe(self) -> Dict[str, Any]:
        info = (self.coordinator.data or {}).get("student_info")
        return dane_testowe(self._typ, getattr(info, "name", "") or "")

    async def async_press(self) -> None:
        opcje = self._config_entry.options
        ma_sms = bool(opcje.get(CONF_SMS_ENABLED)) and bool(
            podziel_adresy(opcje.get("sms_url_oceny" if self._typ == TYP_OCENA else "sms_url_uwagi", ""))
        )
        ma_push = bool(podziel_uslugi_notify(opcje.get(CONF_PUSH_NOTIFY, "")))
        if not ma_sms and not ma_push:
            raise HomeAssistantError(
                "Brak skonfigurowanych kanalow: wlacz bramke SMS i podaj adresy lub uslugi push "
                "(Ustawienia -> Integracje -> Librus -> Konfiguruj)."
            )

        wynik = await async_powiadom(self.hass, opcje, self._typ, self._dane_testowe())
        _LOGGER.info("Test powiadomien (%s): SMS %d, push %d", self._typ, wynik["sms"], wynik["push"])
        if wynik["sms"] + wynik["push"] == 0:
            raise HomeAssistantError(
                "Test nie powiodl sie - zaden kanal nie potwierdzil wysylki. "
                "Sprawdz logi (Ustawienia -> System -> Logi, filtr 'librus')."
            )
