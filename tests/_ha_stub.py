"""Lekkie atrapy modulow Home Assistant, by testowac logike koordynatora bez instalacji HA.

Uzywane tylko gdy prawdziwy homeassistant nie jest zainstalowany (STUBBED == True).
Prawdziwe testy HA (tests/test_init.py) dzialaja z pytest-homeassistant-custom-component.
"""

import sys
import types
from datetime import datetime
from unittest.mock import MagicMock

STUBBED = False


class _Auto(types.ModuleType):
    """Modul, ktorego nieznane atrybuty sa MagicMockami (wystarczy do importow)."""

    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)
        wartosc = MagicMock(name=f"{self.__name__}.{name}")
        setattr(self, name, wartosc)
        return wartosc


class DataUpdateCoordinator:
    def __init__(self, hass, logger, name=None, update_interval=None):
        self.hass = hass
        self.data = None

    def __class_getitem__(cls, item):
        return cls


class CoordinatorEntity:
    def __init__(self, coordinator):
        self.coordinator = coordinator

    def __class_getitem__(cls, item):
        return cls

    async def async_added_to_hass(self):
        pass

    def async_on_remove(self, func):
        pass

    def async_write_ha_state(self):
        pass


class SensorEntity:
    pass


class Store:
    wczytane = None

    def __init__(self, hass, version, key):
        self.key = key
        self.zapisane = None

    async def async_load(self):
        return Store.wczytane

    async def async_save(self, dane):
        self.zapisane = dane


class UpdateFailed(Exception):
    pass


class HomeAssistantError(Exception):
    pass


class ServiceValidationError(HomeAssistantError):
    pass


def _modul(nazwa, **atrybuty):
    m = _Auto(nazwa)
    for k, v in atrybuty.items():
        setattr(m, k, v)
    sys.modules[nazwa] = m
    return m


def install() -> bool:
    global STUBBED
    try:
        import homeassistant  # noqa: F401
        return False
    except ImportError:
        pass

    dt = _modul(
        "homeassistant.util.dt",
        now=lambda: datetime.now().astimezone(),
    )
    util = _modul(
        "homeassistant.util",
        dt=dt,
        slugify=lambda s: "".join(c if c.isalnum() else "_" for c in str(s).lower()).strip("_"),
    )
    _modul("homeassistant", util=util)
    _modul("homeassistant.components")
    _modul("homeassistant.components.sensor", SensorEntity=SensorEntity)
    _modul("homeassistant.components.http")
    _modul("homeassistant.components.frontend")
    _modul("homeassistant.config_entries")
    _modul("homeassistant.const", CONF_USERNAME="username", CONF_PASSWORD="password")
    _modul(
        "homeassistant.core",
        callback=lambda f: f,
        SupportsResponse=MagicMock(),
    )
    _modul(
        "homeassistant.exceptions",
        HomeAssistantError=HomeAssistantError,
        ServiceValidationError=ServiceValidationError,
    )
    _modul("homeassistant.helpers")
    _modul("homeassistant.helpers.config_validation")
    _modul("homeassistant.helpers.aiohttp_client")
    _modul("homeassistant.helpers.entity_platform")
    _modul("homeassistant.helpers.event", async_track_time_change=lambda *a, **k: (lambda: None))
    _modul("homeassistant.helpers.storage", Store=Store)
    _modul(
        "homeassistant.helpers.update_coordinator",
        CoordinatorEntity=CoordinatorEntity,
        DataUpdateCoordinator=DataUpdateCoordinator,
        UpdateFailed=UpdateFailed,
    )
    sys.modules["homeassistant.helpers"].config_validation = sys.modules["homeassistant.helpers.config_validation"]
    sys.modules["homeassistant.helpers"].aiohttp_client = sys.modules["homeassistant.helpers.aiohttp_client"]
    try:
        import voluptuous  # noqa: F401
    except ImportError:
        _modul("voluptuous")
    STUBBED = True
    return True


install()
