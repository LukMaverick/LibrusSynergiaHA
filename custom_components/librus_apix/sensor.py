"""Platforma czujników dla integracji Librus APIX."""

import logging
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import DOMAIN, SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)


def _jest_nowa(date_str: str) -> bool:
    """Sprawdz czy data miesci sie w ostatnich 24 godzinach (dzis lub wczoraj)."""
    if not date_str:
        return False
    wczoraj = date.today() - timedelta(days=1)
    for fmt in (
        "%d.%m.%Y %H:%M:%S",
        "%d.%m.%Y %H:%M",
        "%d.%m.%Y",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d",
    ):
        try:
            d = datetime.strptime(date_str.strip(), fmt).date()
            return d >= wczoraj
        except ValueError:
            continue
    return False


def _srednia_ocen(oceny: List[Dict]) -> Optional[float]:
    """Oblicz srednia ocen z listy ocen."""
    wartosci = []
    for g in oceny:
        grade_str = g.get("ocena", "")
        try:
            base = float(grade_str[0])
            if len(grade_str) > 1:
                if "+" in grade_str:
                    base += 0.5
                elif "-" in grade_str:
                    base -= 0.25
            wartosci.append(base)
        except (ValueError, IndexError):
            continue
    return round(sum(wartosci) / len(wartosci), 2) if wartosci else None


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Konfiguracja platformy czujnikow Librus APIX."""
    client = hass.data[DOMAIN][config_entry.entry_id]

    coordinator = LibrusDataUpdateCoordinator(hass, client)
    await coordinator.async_config_entry_first_refresh()

    entities: List[SensorEntity] = [
        LibrusUczenSensor(coordinator, config_entry),
        LibrusSzczesliwyNumerekSensor(coordinator, config_entry),
        LibrusOcenySensor(coordinator, config_entry),
        LibrusWiadomosciSensor(coordinator, config_entry),
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


EVENT_NOWA_WIADOMOSC = f"{DOMAIN}_nowa_wiadomosc"
EVENT_NOWA_OCENA = f"{DOMAIN}_nowa_ocena"
EVENT_NOWE_ZADANIE = f"{DOMAIN}_nowe_zadanie"
EVENT_NOWE_ZDARZENIE = f"{DOMAIN}_nowe_zdarzenie"


class LibrusDataUpdateCoordinator(DataUpdateCoordinator):
    """Klasa zarzadzajaca pobieraniem danych z Librus."""

    def __init__(self, hass: HomeAssistant, client: Any) -> None:
        """Inicjalizacja koordynatora."""
        self.client = client
        self._seen_message_hrefs: set = set()
        self._seen_grade_ids: set = set()
        self._seen_homework_ids: set = set()
        self._seen_schedule_ids: set = set()
        self._first_run: bool = True
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )

    async def _async_update_data(self) -> Dict[str, Any]:
        """Pobierz aktualne dane z API Librus."""
        from datetime import date as _date
        current_sem = 1 if _date.today().month >= 9 else 2

        try:
            student_info = await self.client.async_get_student_information()
            grades = await self.client.async_get_grades()
            messages = await self.client.async_get_messages(count=10)
            homework_raw = await self.client.async_get_homework()
            schedule_raw = await self.client.async_get_schedule()

            if grades is None:
                # Zachowaj poprzednie dane o ocenach jesli dostepne, wiadomosci zaktualizuj jesli OK
                prev = self.data or {}
                if not prev.get("oceny"):
                    raise UpdateFailed("Nie udalo sie pobrac ocen i brak danych w cache")
                _LOGGER.warning("Nie udalo sie pobrac ocen - uzywam poprzednich danych z cache")
                return {
                    "student_info": student_info or prev.get("student_info"),
                    "oceny": prev.get("oceny", []),
                    "oceny_wg_przedmiotu": prev.get("oceny_wg_przedmiotu", {}),
                    "wiadomosci": (
                        self._build_wiadomosci(messages)
                        if messages is not None
                        else prev.get("wiadomosci", [])
                    ),
                    "zadania": (
                        self._build_zadania(homework_raw)
                        if homework_raw is not None
                        else prev.get("zadania", [])
                    ),
                    "terminarz": (
                        schedule_raw
                        if schedule_raw is not None
                        else prev.get("terminarz", [])
                    ),
                }

            # Grupuj oceny wg przedmiotu i oznacz nowe
            oceny_wg_przedmiotu: Dict[str, List[Dict]] = {}
            for grade in grades:
                subject = grade["subject"]
                if subject not in oceny_wg_przedmiotu:
                    oceny_wg_przedmiotu[subject] = []
                oceny_wg_przedmiotu[subject].append({
                    "ocena": grade["grade"],
                    "data": grade["date"],
                    "kategoria": grade["category"],
                    "nauczyciel": grade["teacher"],
                    "semestr": grade.get("semester"),
                    "jest_nowa": _jest_nowa(grade["date"]),
                })

            wiadomosci = self._build_wiadomosci(messages)
            zadania = self._build_zadania(homework_raw)
            terminarz = schedule_raw if schedule_raw is not None else []

            result = {
                "student_info": student_info,
                "oceny": grades,
                "oceny_wg_przedmiotu": oceny_wg_przedmiotu,
                "wiadomosci": wiadomosci,
                "zadania": zadania,
                "terminarz": terminarz,
                "semestr_biezacy": current_sem,
            }

            # Pierwsze pobranie - tylko zapamietaj stan, nie wysylaj powiadomien
            if self._first_run:
                self._first_run = False
                for msg in wiadomosci:
                    self._seen_message_hrefs.add(msg["href"])
                for grade in grades:
                    self._seen_grade_ids.add(
                        (grade["subject"], grade["date"], grade["grade"])
                    )
                for zadanie in zadania:
                    self._seen_homework_ids.add(
                        (zadanie["przedmiot"], zadanie["termin"], zadanie["kategoria"])
                    )
                for zdarzenie in terminarz:
                    self._seen_schedule_ids.add(
                        (zdarzenie["data"], zdarzenie["tytul"], zdarzenie["przedmiot"])
                    )
            else:
                self._fire_events(wiadomosci, grades)
                self._fire_homework_events(zadania)
                self._fire_schedule_events(terminarz)

            return result

        except UpdateFailed:
            raise
        except Exception as err:
            raise UpdateFailed(f"Blad komunikacji z API: {err}") from err

    def _fire_events(self, messages: List[Dict], grades: List[Dict]) -> None:
        """Wyslij zdarzenia HA dla nowych wiadomosci i ocen."""
        for msg in messages:
            href = msg.get("href", "")
            if href and href not in self._seen_message_hrefs:
                self._seen_message_hrefs.add(href)
                _LOGGER.debug("Nowa wiadomosc: %s", msg.get("title"))
                self.hass.bus.fire(
                    EVENT_NOWA_WIADOMOSC,
                    {
                        "nadawca": msg.get("author", ""),
                        "temat": msg.get("title", ""),
                        "data": msg.get("date", ""),
                        "ma_zalacznik": msg.get("has_attachment", False),
                    },
                )

        for grade in grades:
            grade_id = (grade["subject"], grade["date"], grade["grade"])
            if grade_id not in self._seen_grade_ids:
                self._seen_grade_ids.add(grade_id)
                _LOGGER.debug("Nowa ocena: %s %s", grade["subject"], grade["grade"])
                self.hass.bus.fire(
                    EVENT_NOWA_OCENA,
                    {
                        "przedmiot": grade["subject"],
                        "ocena": grade["grade"],
                        "data": grade["date"],
                        "kategoria": grade["category"],
                        "nauczyciel": grade["teacher"],
                    },
                )

    def _fire_schedule_events(self, terminarz: List[Dict]) -> None:
        """Wyslij zdarzenia HA dla nowych zdarzen w kalendarzu."""
        for zdarzenie in terminarz:
            ev_id = (zdarzenie["data"], zdarzenie["tytul"], zdarzenie["przedmiot"])
            if ev_id not in self._seen_schedule_ids:
                self._seen_schedule_ids.add(ev_id)
                _LOGGER.debug("Nowe zdarzenie: %s %s %s", zdarzenie["data"], zdarzenie["przedmiot"], zdarzenie["tytul"])
                self.hass.bus.fire(
                    EVENT_NOWE_ZDARZENIE,
                    {
                        "data": zdarzenie["data"],
                        "tytul": zdarzenie["tytul"],
                        "przedmiot": zdarzenie["przedmiot"],
                        "godzina": zdarzenie["godzina"],
                    },
                )

    def _build_wiadomosci(self, messages: Optional[List[Dict]]) -> List[Dict]:
        """Oznacz nowe wiadomosci i zwroc liste."""
        result = []
        for msg in messages or []:
            msg["jest_nowa"] = _jest_nowa(msg.get("date", ""))
            result.append(msg)
        return result

    def _build_zadania(self, homework_raw) -> List[Dict]:
        """Przetworz liste Homework na liste dict, posortowana po terminie."""
        if not homework_raw:
            return []
        zadania = [
            {
                "przedmiot": hw.subject,
                "kategoria": hw.category,
                "nauczyciel": hw.teacher,
                "lekcja": hw.lesson,
                "data_zadania": hw.task_date,
                "termin": hw.completion_date,
                "href": hw.href,
            }
            for hw in homework_raw
        ]
        return sorted(zadania, key=lambda z: z["termin"])

    def _fire_homework_events(self, zadania: List[Dict]) -> None:
        """Wyslij zdarzenia HA dla nowych zadan/sprawdzianow."""
        for zadanie in zadania:
            hw_id = (zadanie["przedmiot"], zadanie["termin"], zadanie["kategoria"])
            if hw_id not in self._seen_homework_ids:
                self._seen_homework_ids.add(hw_id)
                _LOGGER.debug("Nowe zadanie: %s %s", zadanie["przedmiot"], zadanie["kategoria"])
                self.hass.bus.fire(
                    EVENT_NOWE_ZADANIE,
                    {
                        "przedmiot": zadanie["przedmiot"],
                        "kategoria": zadanie["kategoria"],
                        "termin": zadanie["termin"],
                        "nauczyciel": zadanie["nauczyciel"],
                    },
                )


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
        return {
            "klasa": info.class_name,
            "numer_w_klasie": info.number,
            "wychowawca": info.tutor,
            "szkola": info.school,
            "szczesliwy_numerek": info.lucky_number,
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

        return {
            "oceny": oceny,
            "lista_ocen": ", ".join(g["ocena"] for g in oceny),
            "srednia": srednia,
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
        return {
            "przedmiot": self._subject,
            "lista_ocen": ", ".join(g["ocena"] for g in oceny),
            "liczba_ocen": len(oceny),
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
        }
