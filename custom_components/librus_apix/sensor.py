"""Platforma czujników dla integracji Librus APIX."""

import logging
from datetime import date, datetime
from typing import Any, Dict, List, Optional

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity, DataUpdateCoordinator

from .const import DOMAIN
from .coordinator import LibrusDataUpdateCoordinator, _jest_nowa, _srednia_ocen

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Konfiguracja platformy czujnikow Librus APIX."""
    coordinator: LibrusDataUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]["coordinator"]

    entities: List[SensorEntity] = [
        LibrusUczenSensor(coordinator, config_entry),
        LibrusSzczesliwyNumerekSensor(coordinator, config_entry),
        LibrusOcenySensor(coordinator, config_entry),
        LibrusOstatniaNowaOcenaSensor(coordinator, config_entry),
        LibrusWiadomosciSensor(coordinator, config_entry),
        LibrusOstatniaNowaWiadomoscSensor(coordinator, config_entry),
        LibrusUwagiSensor(coordinator, config_entry),
        LibrusOstatniaNowaUwagaSensor(coordinator, config_entry),
        LibrusZadaniaSensor(coordinator, config_entry),
        LibrusTerminarzSensor(coordinator, config_entry),
    ]

    # Tworz czujniki per przedmiot na podstawie pierwszego pobrania danych
    for subject in coordinator.data.get("oceny_wg_przedmiotu", {}).keys():
        entities.append(LibrusPrzedmiotSensor(coordinator, subject, config_entry))
        entities.append(LibrusSredniaPrzedmiotuSensor(coordinator, subject, config_entry))

    # Czujnik globalnej sredniej
    entities.append(LibrusSredniaOcenSensor(coordinator, config_entry))

    async_add_entities(entities)


def _device_info(coordinator: DataUpdateCoordinator, config_entry: ConfigEntry) -> Dict[str, Any]:
    """Zwroc informacje o urzadzeniu."""
    data = coordinator.data or {}
    student_info = data.get("student_info")
    name = student_info.name if student_info else "Librus"
    return {
        "identifiers": {(DOMAIN, config_entry.entry_id)},
        "name": f"Librus - {name}",
        "manufacturer": "Librus",
        "model": "Synergia",
    }


class LibrusUczenSensor(CoordinatorEntity, SensorEntity):
    """Czujnik z informacjami o uczniu."""

    def __init__(self, coordinator: LibrusDataUpdateCoordinator, config_entry: ConfigEntry) -> None:
        """Inicjalizacja."""
        super().__init__(coordinator)
        self._config_entry = config_entry
        self._attr_has_entity_name = False
        self._attr_name = "Informacje o uczniu"
        self._attr_unique_id = f"{config_entry.entry_id}_uczen"
        self._attr_icon = "mdi:account-school"

    @property
    def device_info(self) -> Dict[str, Any]:
        return _device_info(self.coordinator, self._config_entry)

    @property
    def native_value(self) -> Optional[str]:
        info = (self.coordinator.data or {}).get("student_info")
        return info.name if info else None

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        info = (self.coordinator.data or {}).get("student_info")
        if not info:
            return {}
        data = self.coordinator.data or {}
        return {
            "klasa": info.class_name,
            "numer_w_klasie": info.number,
            "wychowawca": info.tutor,
            "szkola": info.school,
            "szczesliwy_numerek": info.lucky_number,
            "tryb_sprawdzania": data.get("tryb_sprawdzania"),
            "interwal_minuty": data.get("interwal_minuty"),
        }


class LibrusSzczesliwyNumerekSensor(CoordinatorEntity, SensorEntity):
    """Czujnik ze szczesliwym numerkiem dnia."""

    def __init__(self, coordinator: LibrusDataUpdateCoordinator, config_entry: ConfigEntry) -> None:
        """Inicjalizacja."""
        super().__init__(coordinator)
        self._config_entry = config_entry
        self._attr_has_entity_name = False
        self._attr_name = "Szczesliwy numerek"
        self._attr_unique_id = f"{config_entry.entry_id}_szczesliwy_numerek"
        self._attr_icon = "mdi:numeric"

    @property
    def device_info(self) -> Dict[str, Any]:
        return _device_info(self.coordinator, self._config_entry)

    @property
    def native_value(self) -> Any:
        info = (self.coordinator.data or {}).get("student_info")
        return info.lucky_number if info else None


class LibrusOcenySensor(CoordinatorEntity, SensorEntity):
    """Czujnik z wszystkimi ocenami pogrupowanymi wedlug przedmiotow."""

    def __init__(self, coordinator: LibrusDataUpdateCoordinator, config_entry: ConfigEntry) -> None:
        """Inicjalizacja."""
        super().__init__(coordinator)
        self._config_entry = config_entry
        self._attr_has_entity_name = False
        self._attr_name = "Oceny"
        self._attr_unique_id = f"{config_entry.entry_id}_oceny"
        self._attr_icon = "mdi:school"

    @property
    def device_info(self) -> Dict[str, Any]:
        return _device_info(self.coordinator, self._config_entry)

    @property
    def native_value(self) -> int:
        return len((self.coordinator.data or {}).get("oceny", []))

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        data = self.coordinator.data or {}
        oceny_wg_przedmiotu = data.get("oceny_wg_przedmiotu", {})
        sa_nowe = any(
            g["jest_nowa"]
            for grades in oceny_wg_przedmiotu.values()
            for g in grades
        )
        return {
            "oceny_wg_przedmiotu": oceny_wg_przedmiotu,
            "liczba_ocen": len((self.coordinator.data or {}).get("oceny", [])),
            "liczba_przedmiotow": len(oceny_wg_przedmiotu),
            "sa_nowe_oceny": sa_nowe,
            "semestr": data.get("semestr_biezacy"),
            "ostatnia_nowa_ocena": (data.get("ostatnia_nowa_ocena") or {}).get("ocena"),
            "ostatnia_nowa_ocena_przedmiot": (data.get("ostatnia_nowa_ocena") or {}).get("przedmiot"),
            "ostatnia_nowa_ocena_szczegoly": data.get("ostatnia_nowa_ocena"),
        }


class LibrusPrzedmiotSensor(CoordinatorEntity, SensorEntity):
    """Czujnik z ocenami dla konkretnego przedmiotu."""

    def __init__(
        self,
        coordinator: LibrusDataUpdateCoordinator,
        subject: str,
        config_entry: ConfigEntry,
    ) -> None:
        """Inicjalizacja."""
        super().__init__(coordinator)
        self._config_entry = config_entry
        self._subject = subject
        safe_name = subject.lower().replace(" ", "_").replace("/", "_")
        self._attr_has_entity_name = False
        self._attr_name = subject
        self._attr_unique_id = f"{config_entry.entry_id}_przedmiot_{safe_name}"
        self._attr_icon = "mdi:book-open-variant"

    @property
    def device_info(self) -> Dict[str, Any]:
        return _device_info(self.coordinator, self._config_entry)

    @property
    def native_value(self) -> Optional[str]:
        oceny = (self.coordinator.data or {}).get("oceny_wg_przedmiotu", {}).get(self._subject, [])
        if not oceny:
            return None
        return ", ".join(g["ocena"] for g in oceny)

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        oceny = (self.coordinator.data or {}).get("oceny_wg_przedmiotu", {}).get(self._subject, [])
        if not oceny:
            return {}

        srednia = _srednia_ocen(oceny)

        # Najnowsza ocena wg daty
        najnowsza: Optional[Dict] = None
        najnowsza_data: Optional[date] = None
        for g in oceny:
            for fmt in ("%d.%m.%Y", "%Y-%m-%d"):
                try:
                    d = datetime.strptime(g["data"].strip(), fmt).date()
                    if najnowsza_data is None or d > najnowsza_data:
                        najnowsza_data = d
                        najnowsza = g
                    break
                except ValueError:
                    continue

        srednie = ((self.coordinator.data or {}).get("srednie", {}) or {}).get(self._subject, {})
        return {
            "oceny": oceny,
            "lista_ocen": ", ".join(g["ocena"] for g in oceny),
            "srednia": srednia,
            "srednia_librus": srednie.get("librus"),
            "najnowsza_ocena": najnowsza,
            "sa_nowe_oceny": any(g["jest_nowa"] for g in oceny),
        }


class LibrusSredniaOcenSensor(CoordinatorEntity, SensorEntity):
    """Czujnik ze srednia wszystkich ocen biezacego semestru (do wykresu)."""

    def __init__(self, coordinator: LibrusDataUpdateCoordinator, config_entry: ConfigEntry) -> None:
        """Inicjalizacja."""
        super().__init__(coordinator)
        self._config_entry = config_entry
        self._attr_has_entity_name = False
        self._attr_name = "Srednia ocen"
        self._attr_unique_id = f"{config_entry.entry_id}_srednia_ocen"
        self._attr_icon = "mdi:chart-line"
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_native_unit_of_measurement = None

    @property
    def device_info(self) -> Dict[str, Any]:
        return _device_info(self.coordinator, self._config_entry)

    @property
    def native_value(self) -> Optional[float]:
        data = self.coordinator.data or {}
        wszystkie = [
            g
            for oceny in data.get("oceny_wg_przedmiotu", {}).values()
            for g in oceny
        ]
        return _srednia_ocen(wszystkie)

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        data = self.coordinator.data or {}
        srednie_przedmiotow = {
            subject: _srednia_ocen(oceny)
            for subject, oceny in data.get("oceny_wg_przedmiotu", {}).items()
            if _srednia_ocen(oceny) is not None
        }
        return {
            "srednie_wg_przedmiotow": srednie_przedmiotow,
            "semestr": data.get("semestr_biezacy"),
        }


class LibrusSredniaPrzedmiotuSensor(CoordinatorEntity, SensorEntity):
    """Czujnik ze srednia ocen dla konkretnego przedmiotu (do wykresu)."""

    def __init__(
        self,
        coordinator: LibrusDataUpdateCoordinator,
        subject: str,
        config_entry: ConfigEntry,
    ) -> None:
        """Inicjalizacja."""
        super().__init__(coordinator)
        self._config_entry = config_entry
        self._subject = subject
        safe_name = subject.lower().replace(" ", "_").replace("/", "_")
        self._attr_has_entity_name = False
        self._attr_name = f"Srednia {subject}"
        self._attr_unique_id = f"{config_entry.entry_id}_srednia_{safe_name}"
        self._attr_icon = "mdi:chart-bar"
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_native_unit_of_measurement = None

    @property
    def device_info(self) -> Dict[str, Any]:
        return _device_info(self.coordinator, self._config_entry)

    @property
    def native_value(self) -> Optional[float]:
        oceny = (self.coordinator.data or {}).get("oceny_wg_przedmiotu", {}).get(self._subject, [])
        return _srednia_ocen(oceny)

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        oceny = (self.coordinator.data or {}).get("oceny_wg_przedmiotu", {}).get(self._subject, [])
        srednie = ((self.coordinator.data or {}).get("srednie", {}) or {}).get(self._subject, {})
        return {
            "przedmiot": self._subject,
            "lista_ocen": ", ".join(g["ocena"] for g in oceny),
            "liczba_ocen": len(oceny),
            "srednia_librus": srednie.get("librus"),
        }


class LibrusTerminarzSensor(CoordinatorEntity, SensorEntity):
    """Czujnik z nadchodzacymi zdarzeniami z kalendarza Librusa (biezacy + nastepny miesiac)."""

    def __init__(self, coordinator: LibrusDataUpdateCoordinator, config_entry: ConfigEntry) -> None:
        """Inicjalizacja."""
        super().__init__(coordinator)
        self._config_entry = config_entry
        self._attr_has_entity_name = False
        self._attr_name = "Terminarz"
        self._attr_unique_id = f"{config_entry.entry_id}_terminarz"
        self._attr_icon = "mdi:calendar-month"

    @property
    def device_info(self) -> Dict[str, Any]:
        return _device_info(self.coordinator, self._config_entry)

    @property
    def native_value(self) -> int:
        return len((self.coordinator.data or {}).get("terminarz", []))

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        terminarz = (self.coordinator.data or {}).get("terminarz", [])
        typy: Dict[str, int] = {}
        for z in terminarz:
            t = z.get("tytul", "")
            typy[t] = typy.get(t, 0) + 1
        return {
            "zdarzenia": terminarz,
            "liczba_zdarzen": len(terminarz),
            "typy": typy,
        }


class LibrusZadaniaSensor(CoordinatorEntity, SensorEntity):
    """Czujnik z nadchodzacymi zadaniami i sprawdzianami (30 dni do przodu)."""

    def __init__(self, coordinator: LibrusDataUpdateCoordinator, config_entry: ConfigEntry) -> None:
        """Inicjalizacja."""
        super().__init__(coordinator)
        self._config_entry = config_entry
        self._attr_has_entity_name = False
        self._attr_name = "Zadania"
        self._attr_unique_id = f"{config_entry.entry_id}_zadania"
        self._attr_icon = "mdi:calendar-check"

    @property
    def device_info(self) -> Dict[str, Any]:
        return _device_info(self.coordinator, self._config_entry)

    @property
    def native_value(self) -> int:
        return len((self.coordinator.data or {}).get("zadania", []))

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        zadania = (self.coordinator.data or {}).get("zadania", [])
        kategorie: Dict[str, int] = {}
        for z in zadania:
            k = z.get("kategoria", "")
            kategorie[k] = kategorie.get(k, 0) + 1
        return {
            "zadania": zadania,
            "liczba_zadan": len(zadania),
            "kategorie": kategorie,
        }


class LibrusWiadomosciSensor(CoordinatorEntity, SensorEntity):
    """Czujnik z wiadomosciami (temat i nadawca, bez pobierania tresci)."""

    def __init__(self, coordinator: LibrusDataUpdateCoordinator, config_entry: ConfigEntry) -> None:
        """Inicjalizacja."""
        super().__init__(coordinator)
        self._config_entry = config_entry
        self._attr_has_entity_name = False
        self._attr_name = "Wiadomosci"
        self._attr_unique_id = f"{config_entry.entry_id}_wiadomosci"
        self._attr_icon = "mdi:message-text"

    @property
    def device_info(self) -> Dict[str, Any]:
        return _device_info(self.coordinator, self._config_entry)

    @property
    def native_value(self) -> int:
        """Liczba nieprzeczytanych wiadomosci."""
        msgs = (self.coordinator.data or {}).get("wiadomosci", [])
        return sum(1 for m in msgs if m.get("unread", False))

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        msgs = (self.coordinator.data or {}).get("wiadomosci", [])[:5]
        return {
            "wiadomosci": [
                {
                    "nadawca": m["author"],
                    "temat": m["title"],
                    "data": m["date"],
                    "nieprzeczytana": m.get("unread", False),
                    "jest_nowa": m.get("jest_nowa", False),
                    "ma_zalacznik": m.get("has_attachment", False),
                }
                for m in msgs
            ],
            "liczba_nieprzeczytanych": sum(1 for m in msgs if m.get("unread", False)),
            "sa_nowe_wiadomosci": any(m.get("jest_nowa", False) for m in msgs),
            "ostatnia_nowa_wiadomosc": (self.coordinator.data or {}).get("ostatnia_nowa_wiadomosc"),
        }


def _skroc(tekst: Optional[str], maks: int = 250) -> Optional[str]:
    """Skroc tekst do limitu stanu encji HA (255 znakow)."""
    if tekst is None:
        return None
    tekst = str(tekst)
    return tekst if len(tekst) <= maks else tekst[: maks - 1] + "\u2026"


class LibrusOstatniaNowaOcenaSensor(CoordinatorEntity, SensorEntity):
    """Czujnik 'Ostatnia nowa ocena' - stan to ocena, przedmiot w atrybutach.

    Pokazuje ostatnia ocene wykryta jako nowa przy odswiezaniu (pamietana w magazynie HA,
    wiec przezywa restart). Zanim jakakolwiek nowa ocena zostanie wykryta - najnowsza wg daty.
    """

    def __init__(self, coordinator: LibrusDataUpdateCoordinator, config_entry: ConfigEntry) -> None:
        """Inicjalizacja."""
        super().__init__(coordinator)
        self._config_entry = config_entry
        self._attr_has_entity_name = False
        self._attr_name = "Ostatnia nowa ocena"
        self._attr_unique_id = f"{config_entry.entry_id}_ostatnia_nowa_ocena"
        self._attr_icon = "mdi:star-outline"

    @property
    def device_info(self) -> Dict[str, Any]:
        return _device_info(self.coordinator, self._config_entry)

    @property
    def native_value(self) -> Optional[str]:
        ocena = (self.coordinator.data or {}).get("ostatnia_nowa_ocena") or {}
        return ocena.get("ocena") or None

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        ocena = (self.coordinator.data or {}).get("ostatnia_nowa_ocena") or {}
        return {
            "przedmiot": ocena.get("przedmiot"),
            "data": ocena.get("data"),
            "kategoria": ocena.get("kategoria"),
            "nauczyciel": ocena.get("nauczyciel"),
            "waga": ocena.get("waga"),
            "liczy_do_sredniej": ocena.get("liczy_do_sredniej"),
            "komentarz": ocena.get("komentarz"),
            "srednia": ocena.get("srednia"),
            "srednia_librus": ocena.get("srednia_librus"),
            "uczen": ocena.get("uczen"),
        }


class LibrusOstatniaNowaWiadomoscSensor(CoordinatorEntity, SensorEntity):
    """Czujnik 'Ostatnia nowa wiadomosc' - stan to temat, reszta w atrybutach."""

    def __init__(self, coordinator: LibrusDataUpdateCoordinator, config_entry: ConfigEntry) -> None:
        """Inicjalizacja."""
        super().__init__(coordinator)
        self._config_entry = config_entry
        self._attr_has_entity_name = False
        self._attr_name = "Ostatnia nowa wiadomosc"
        self._attr_unique_id = f"{config_entry.entry_id}_ostatnia_nowa_wiadomosc"
        self._attr_icon = "mdi:email-newsletter"

    @property
    def device_info(self) -> Dict[str, Any]:
        return _device_info(self.coordinator, self._config_entry)

    @property
    def native_value(self) -> Optional[str]:
        msg = (self.coordinator.data or {}).get("ostatnia_nowa_wiadomosc") or {}
        return _skroc(msg.get("temat")) or None

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        msg = (self.coordinator.data or {}).get("ostatnia_nowa_wiadomosc") or {}
        return {
            "nadawca": msg.get("nadawca"),
            "temat": msg.get("temat"),
            "data": msg.get("data"),
            "nieprzeczytana": msg.get("nieprzeczytana"),
            "ma_zalacznik": msg.get("ma_zalacznik"),
        }


class LibrusUwagiSensor(CoordinatorEntity, SensorEntity):
    """Czujnik z uwagami ucznia - stan to liczba uwag, lista w atrybutach."""

    def __init__(self, coordinator: LibrusDataUpdateCoordinator, config_entry: ConfigEntry) -> None:
        """Inicjalizacja."""
        super().__init__(coordinator)
        self._config_entry = config_entry
        self._attr_has_entity_name = False
        self._attr_name = "Uwagi"
        self._attr_unique_id = f"{config_entry.entry_id}_uwagi"
        self._attr_icon = "mdi:comment-alert"

    @property
    def device_info(self) -> Dict[str, Any]:
        return _device_info(self.coordinator, self._config_entry)

    @property
    def native_value(self) -> int:
        return len((self.coordinator.data or {}).get("uwagi", []))

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        data = self.coordinator.data or {}
        uwagi = data.get("uwagi", [])
        rodzaje: Dict[str, int] = {}
        for u in uwagi:
            r = u.get("rodzaj", "") or "inne"
            rodzaje[r] = rodzaje.get(r, 0) + 1
        return {
            "uwagi": uwagi,
            "liczba_uwag": len(uwagi),
            "rodzaje": rodzaje,
            "sa_nowe_uwagi": any(_jest_nowa(u.get("data", "")) for u in uwagi),
            "ostatnia_nowa_uwaga": data.get("ostatnia_nowa_uwaga"),
        }


class LibrusOstatniaNowaUwagaSensor(CoordinatorEntity, SensorEntity):
    """Czujnik 'Ostatnia nowa uwaga' - stan to tresc (skrocona), reszta w atrybutach."""

    def __init__(self, coordinator: LibrusDataUpdateCoordinator, config_entry: ConfigEntry) -> None:
        """Inicjalizacja."""
        super().__init__(coordinator)
        self._config_entry = config_entry
        self._attr_has_entity_name = False
        self._attr_name = "Ostatnia nowa uwaga"
        self._attr_unique_id = f"{config_entry.entry_id}_ostatnia_nowa_uwaga"
        self._attr_icon = "mdi:comment-text-outline"

    @property
    def device_info(self) -> Dict[str, Any]:
        return _device_info(self.coordinator, self._config_entry)

    @property
    def native_value(self) -> Optional[str]:
        uwaga = (self.coordinator.data or {}).get("ostatnia_nowa_uwaga") or {}
        return _skroc(uwaga.get("tresc")) or None

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        uwaga = (self.coordinator.data or {}).get("ostatnia_nowa_uwaga") or {}
        return {
            "tresc": uwaga.get("tresc"),
            "rodzaj": uwaga.get("rodzaj"),
            "kategoria": uwaga.get("kategoria"),
            "nauczyciel": uwaga.get("nauczyciel"),
            "data": uwaga.get("data"),
        }
