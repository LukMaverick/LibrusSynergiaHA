"""Platforma czujników dla integracji Librus APIX."""

import asyncio
import logging
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_USERNAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_time_change
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)
from homeassistant.util import dt as dt_util
from homeassistant.util import slugify

from .const import (
    DOMAIN,
    SCAN_INTERVAL,
    TIMETABLE_REFRESH,
    TYDZIEN_CACHE_TTL,
    TYDZIEN_OKNO_NAPRZOD,
    TYDZIEN_OKNO_WSTECZ,
    VERSION,
    ZADANIA_TRESC_HORYZONT_DNI,
    ZADANIA_TRESC_LIMIT_NA_CYKL,
)
from .plan import (
    najblizszy_dzien_nauki,
    parse_iso,
    poniedzialek,
    przytnij_do_okna,
    wybierz_tydzien,
)
from .scalanie import pusty_dzien, scal, zbuduj_tydzien
from .zadania import (
    do_pobrania_tresci,
    do_zrobienia,
    normalizuj_zadania,
    odswiez_pilnosc,
    podsumuj_otwarte,
    tresc_ze_szczegolow,
    zadanie_legacy,
)

_LOGGER = logging.getLogger(__name__)

ZADANIA_BLAD_MAX = timedelta(hours=24)


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


def _slug_i_imie(hass: HomeAssistant, config_entry: ConfigEntry, coordinator: Any) -> tuple:
    """Zwroc (slug, imie) ucznia dla entity_id; slug zapisujemy w opcjach, zeby byl stabilny."""
    info = (coordinator.data or {}).get("student_info")
    pelne = (getattr(info, "name", "") or "").strip()
    imie = pelne.split()[0] if pelne else ""
    slug = config_entry.options.get("slug")
    if not slug:
        slug = slugify(imie) or slugify(config_entry.data.get(CONF_USERNAME, "")) or "uczen"
        hass.config_entries.async_update_entry(
            config_entry, options={**config_entry.options, "slug": slug}
        )
    return slug, imie or slug.capitalize()


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Konfiguracja platformy czujnikow Librus APIX."""
    dane = hass.data[DOMAIN][config_entry.entry_id]
    client = dane["client"]

    coordinator = LibrusDataUpdateCoordinator(hass, client, config_entry)
    await coordinator.async_config_entry_first_refresh()
    dane["coordinator"] = coordinator

    slug, imie = _slug_i_imie(hass, config_entry, coordinator)

    entities: List[SensorEntity] = [
        LibrusUczenSensor(coordinator, config_entry),
        LibrusSzczesliwyNumerekSensor(coordinator, config_entry),
        LibrusOcenySensor(coordinator, config_entry),
        LibrusWiadomosciSensor(coordinator, config_entry),
        LibrusZadaniaSensor(coordinator, config_entry),
        LibrusTerminarzSensor(coordinator, config_entry),
        LibrusPlanDzisSensor(coordinator, config_entry, slug, imie),
        LibrusPlanJutroSensor(coordinator, config_entry, slug, imie),
        LibrusNastepnaLekcjaSensor(coordinator, config_entry, slug, imie),
        LibrusPlanTygodniaSensor(coordinator, config_entry, slug, imie),
        LibrusDoZrobieniaJutroSensor(coordinator, config_entry, slug, imie),
        LibrusZadaniaOtwarteSensor(coordinator, config_entry, slug, imie),
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

    def __init__(self, hass: HomeAssistant, client: Any, config_entry: Optional[ConfigEntry] = None) -> None:
        """Inicjalizacja koordynatora."""
        self.client = client
        self._seen_message_hrefs: set = set()
        self._seen_grade_ids: set = set()
        self._seen_homework_ids: set = set()
        self._seen_schedule_ids: set = set()
        self._first_run: bool = True
        # Plan lekcji: pobierany rzadziej niz reszta danych
        self._plan: Optional[Dict[str, Any]] = None
        self._plan_pobrano: Optional[datetime] = None
        self._plan_blad: bool = False
        # Tresci zadan (id -> tresc), trwale w Store
        self._tresci: Dict[str, str] = {}
        self._tresci_wczytane: bool = False
        self._store: Optional[Store] = (
            Store(hass, 1, f"{DOMAIN}_{config_entry.entry_id}_tresci") if config_entry else None
        )
        self._zadania_blad_od: Optional[datetime] = None
        self._zadania_aktualne: bool = True
        # Cache tygodni pobieranych uslugą pobierz_tydzien
        self._cache_tygodni: Dict[str, tuple] = {}
        self._blokada_tygodnia = asyncio.Lock()
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )

    # ------------------------------------------------------------------ pobieranie

    async def _async_wczytaj_tresci(self) -> None:
        if self._tresci_wczytane:
            return
        self._tresci_wczytane = True
        if self._store is None:
            return
        zapisane = await self._store.async_load()
        if isinstance(zapisane, dict):
            self._tresci = {str(k): str(v) for k, v in zapisane.items()}

    async def _async_dolacz_tresci(self, zadania: List[Dict[str, Any]]) -> None:
        """Doczytaj tresc nowych zadan z najblizszych dni (limit zapytan na cykl)."""
        zmiana = False
        for z in do_pobrania_tresci(
            zadania, self._tresci, ZADANIA_TRESC_HORYZONT_DNI, ZADANIA_TRESC_LIMIT_NA_CYKL
        ):
            szczegoly = await self.client.async_get_homework_detail(z["href"])
            if szczegoly is None:
                continue  # blad - sprobujemy w nastepnym cyklu
            # pusty wpis oznacza "pobrano, brak rozpoznanej tresci" (nie pytamy ponownie)
            tresc = tresc_ze_szczegolow(szczegoly)
            self._tresci[z["id"]] = tresc or ""
            z["tresc"] = tresc
            zmiana = True
        # Sprzatanie wpisow dla zadan, ktorych juz nie ma
        aktualne_id = {z["id"] for z in zadania}
        for stare in [k for k in self._tresci if k not in aktualne_id]:
            del self._tresci[stare]
            zmiana = True
        if zmiana and self._store is not None:
            await self._store.async_save(dict(self._tresci))

    async def _async_plan(self, now: datetime, today: date) -> Dict[str, Any]:
        """Zwroc plan lekcji, odswiezajac go co TIMETABLE_REFRESH i po zmianie daty."""
        nieaktualny = (
            self._plan is None
            or self._plan_pobrano is None
            or self._plan_pobrano.date() != today
            or now - self._plan_pobrano >= TIMETABLE_REFRESH
        )
        if nieaktualny:
            wynik = await self.client.async_get_timetable(start=today, weeks=2)
            if wynik is not None:
                self._plan, self._plan_pobrano, self._plan_blad = wynik, now, False
            else:
                self._plan_blad = True
                _LOGGER.warning("Nie udalo sie pobrac planu lekcji - uzywam poprzednich danych")
        return self._plan or {"dni": {}, "godziny": {}, "braki": []}

    async def _async_update_data(self) -> Dict[str, Any]:
        """Pobierz aktualne dane z API Librus."""
        now = dt_util.now()
        today = now.date()
        current_sem = 1 if today.month >= 9 else 2

        try:
            await self._async_wczytaj_tresci()
            student_info = await self.client.async_get_student_information()
            grades = await self.client.async_get_grades()
            messages = await self.client.async_get_messages(count=10)
            homework_raw = await self.client.async_get_homework()
            schedule_raw = await self.client.async_get_schedule()
            plan = await self._async_plan(now, today)

            prev = self.data or {}

            if grades is None:
                # Zachowaj poprzednie dane o ocenach jesli dostepne, reszte zaktualizuj
                if not prev.get("oceny"):
                    raise UpdateFailed("Nie udalo sie pobrac ocen i brak danych w cache")
                _LOGGER.warning("Nie udalo sie pobrac ocen - uzywam poprzednich danych z cache")
                oceny = prev.get("oceny", [])
                oceny_wg_przedmiotu = prev.get("oceny_wg_przedmiotu", {})
                student_info = student_info or prev.get("student_info")
                oceny_ok = False
            else:
                oceny = grades
                oceny_ok = True
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

            wiadomosci = (
                self._build_wiadomosci(messages)
                if messages is not None
                else prev.get("wiadomosci", [])
            )

            # Zadania: przy bledzie zachowaj poprzednie dane; po 24 h bledow zaloz brak zadan
            if homework_raw is None:
                zadania_norm = prev.get("zadania_norm", [])
                if self._zadania_blad_od is None:
                    self._zadania_blad_od = now
                elif now - self._zadania_blad_od > ZADANIA_BLAD_MAX:
                    zadania_norm = []
                self._zadania_aktualne = False
            else:
                self._zadania_blad_od = None
                self._zadania_aktualne = True
                zadania_norm = normalizuj_zadania(homework_raw, today, self._tresci)
                await self._async_dolacz_tresci(zadania_norm)
            zadania_norm = odswiez_pilnosc(zadania_norm, today)
            zadania = [
                zadanie_legacy(z) for z in zadania_norm if z["pilnosc"] != "po_terminie"
            ]

            terminarz = schedule_raw if schedule_raw is not None else prev.get("terminarz", [])
            # Do zdarzen i sensora "Terminarz" bierzemy tylko przyszle wpisy (plan tygodnia widzi caly tydzien)
            terminarz_przyszly = [e for e in terminarz if e["data"] >= today.isoformat()]

            result = {
                "student_info": student_info,
                "oceny": oceny,
                "oceny_wg_przedmiotu": oceny_wg_przedmiotu,
                "wiadomosci": wiadomosci,
                "zadania": zadania,
                "zadania_norm": zadania_norm,
                "zadania_aktualne": self._zadania_aktualne,
                "terminarz": terminarz,
                "plan": plan,
                "plan_scalony": scal(plan["dni"], terminarz, zadania_norm),
                "semestr_biezacy": current_sem,
            }

            # Pierwsze pobranie - tylko zapamietaj stan, nie wysylaj powiadomien
            if self._first_run:
                self._first_run = False
                for msg in wiadomosci:
                    self._seen_message_hrefs.add(msg["href"])
                for grade in oceny:
                    self._seen_grade_ids.add(
                        (grade["subject"], grade["date"], grade["grade"])
                    )
                for zadanie in zadania_norm:
                    self._seen_homework_ids.add(zadanie["id"])
                for zdarzenie in terminarz_przyszly:
                    self._seen_schedule_ids.add(
                        (zdarzenie["data"], zdarzenie["tytul"], zdarzenie["przedmiot"])
                    )
            else:
                self._fire_events(wiadomosci, oceny if oceny_ok else [])
                self._fire_homework_events(zadania_norm, today)
                self._fire_schedule_events(terminarz_przyszly)

            return result

        except UpdateFailed:
            raise
        except Exception as err:
            raise UpdateFailed(f"Blad komunikacji z API: {err}") from err

    # --------------------------------------------------------------- usluga tygodnia

    def pobierz_dzien(self, iso: str) -> Dict[str, Any]:
        """Dzien z planu (scalony z terminarzem i zadaniami) albo pusty dzien."""
        return (self.data or {}).get("plan_scalony", {}).get(iso) or pusty_dzien(iso)

    async def async_pobierz_tydzien(self, dowolna_data: Optional[date]) -> Dict[str, Any]:
        """Zwroc kompaktowy plan wybranego tygodnia (usluga pobierz_tydzien).

        Biezacy i nastepny tydzien pochodza z danych koordynatora (bez zapytan do Librusa),
        pozostale z okna -2..+4 tygodni sa pobierane i cachowane przez TYDZIEN_CACHE_TTL.
        """
        dzis = dt_util.now().date()
        poczatek = przytnij_do_okna(
            dowolna_data or dzis, dzis, TYDZIEN_OKNO_WSTECZ, TYDZIEN_OKNO_NAPRZOD
        )
        if poczatek is None:
            raise ServiceValidationError(
                f"Tydzien poza dozwolonym oknem (-{TYDZIEN_OKNO_WSTECZ}..+{TYDZIEN_OKNO_NAPRZOD} tygodni)"
            )
        klucz = poczatek.isoformat()
        biezacy = poniedzialek(dzis)

        async with self._blokada_tygodnia:
            plan = (self.data or {}).get("plan", {})
            if poczatek in (biezacy, biezacy + timedelta(days=7)) and klucz in {
                poniedzialek(parse_iso(k)).isoformat() for k in plan.get("dni", {}) if parse_iso(k)
            }:
                wynik = zbuduj_tydzien(self.data["plan_scalony"], plan.get("godziny", {}), poczatek)
                wynik["nieaktualne"] = self._plan_blad or klucz in plan.get("braki", [])
                return wynik

            teraz = dt_util.now()
            w_cache = self._cache_tygodni.get(klucz)
            if w_cache and teraz - w_cache[0] < TYDZIEN_CACHE_TTL:
                return w_cache[1]

            tt = await self.client.async_get_timetable(start=poczatek, weeks=1)
            if tt is None:
                if w_cache:
                    return {**w_cache[1], "nieaktualne": True}
                raise HomeAssistantError("Nie udalo sie pobrac planu lekcji dla wybranego tygodnia")
            koniec = poczatek + timedelta(days=6)
            terminarz = await self.client.async_get_schedule(od=poczatek, do=koniec) or []
            homework = await self.client.async_get_homework(
                od=poczatek - timedelta(days=14), do=koniec
            )
            zadania = normalizuj_zadania(homework or [], dzis, self._tresci)
            dni = scal(tt["dni"], terminarz, zadania)
            wynik = zbuduj_tydzien(dni, tt["godziny"], poczatek)
            wynik["nieaktualne"] = bool(tt["braki"]) or homework is None
            self._cache_tygodni[klucz] = (teraz, wynik)
            return wynik

    # ------------------------------------------------------------------ zdarzenia

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

    def _fire_homework_events(self, zadania: List[Dict], today: date) -> None:
        """Wyslij zdarzenia HA dla nowych zadan/sprawdzianow (dedup po id zadania)."""
        for zadanie in zadania:
            if zadanie["id"] in self._seen_homework_ids:
                continue
            self._seen_homework_ids.add(zadanie["id"])
            if zadanie["pilnosc"] == "po_terminie":
                continue
            _LOGGER.debug("Nowe zadanie: %s %s", zadanie["przedmiot"], zadanie["kategoria"])
            termin = parse_iso(zadanie["termin"] or "")
            self.hass.bus.fire(
                EVENT_NOWE_ZADANIE,
                {
                    # pola dotychczasowe (termin = surowy tekst z Librusa)
                    "przedmiot": zadanie["przedmiot"],
                    "kategoria": zadanie["kategoria"],
                    "termin": zadanie["termin_raw"],
                    "nauczyciel": zadanie["nauczyciel"],
                    # nowe pola
                    "id": zadanie["id"],
                    "termin_iso": zadanie["termin"],
                    "dni_do": zadanie["dni_do"],
                    "pilnosc": zadanie["pilnosc"],
                    "tresc": zadanie["tresc"],
                    "dzien_tygodnia_terminu": (
                        ["poniedziałek", "wtorek", "środa", "czwartek", "piątek", "sobota", "niedziela"][
                            termin.weekday()
                        ]
                        if termin
                        else None
                    ),
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

    def _przyszle(self) -> List[Dict]:
        # Koordynator trzyma tez zdarzenia z biezacego tygodnia (dla planu tygodnia)
        dzis = dt_util.now().date().isoformat()
        return [e for e in (self.coordinator.data or {}).get("terminarz", []) if e["data"] >= dzis]

    @property
    def native_value(self) -> int:
        return len(self._przyszle())

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        terminarz = self._przyszle()
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


# ----------------------------------------------------------------------------
# Plan lekcji, plan tygodnia i zadania do zrobienia
# ----------------------------------------------------------------------------


class _LibrusPlanSensor(CoordinatorEntity, SensorEntity):
    """Baza czujnikow planu: jawne entity_id sensor.librus_<slug>_<klucz> i odswiezanie w czasie."""

    _tick_co_minute = False

    def __init__(
        self,
        coordinator: LibrusDataUpdateCoordinator,
        config_entry: ConfigEntry,
        slug: str,
        imie: str,
        klucz: str,
        nazwa: str,
        ikona: str,
    ) -> None:
        super().__init__(coordinator)
        self._config_entry = config_entry
        self._attr_has_entity_name = False
        self._attr_name = f"Librus {imie} - {nazwa}"
        self._attr_unique_id = f"{config_entry.entry_id}_{klucz}"
        self.entity_id = f"sensor.librus_{slug}_{klucz}"
        self._attr_icon = ikona

    @property
    def device_info(self) -> Dict[str, Any]:
        return _device_info(self.coordinator, self._config_entry)

    async def async_added_to_hass(self) -> None:
        """Przelicz stan o polnocy (albo co minute), bez nowego pobierania z API."""
        await super().async_added_to_hass()
        if self._tick_co_minute:
            odliczanie = async_track_time_change(self.hass, self._tick, second=0)
        else:
            odliczanie = async_track_time_change(self.hass, self._tick, hour=0, minute=0, second=5)
        self.async_on_remove(odliczanie)

    @callback
    def _tick(self, _now: datetime) -> None:
        self.async_write_ha_state()

    # pomocnicze
    def _plan_dni(self) -> Dict[str, List[Dict[str, Any]]]:
        return ((self.coordinator.data or {}).get("plan") or {}).get("dni", {})

    def _godziny(self) -> Dict[str, str]:
        return ((self.coordinator.data or {}).get("plan") or {}).get("godziny", {})

    def _iso_jutro(self, dzis: date) -> str:
        """Najblizszy dzien nauki po dzisiaj (w piatek poniedzialek); fallback: jutro."""
        nastepny = najblizszy_dzien_nauki(self._plan_dni(), dzis)
        return (nastepny or dzis + timedelta(days=1)).isoformat()


class LibrusPlanDzisSensor(_LibrusPlanSensor):
    """Plan lekcji na dzisiaj."""

    _unrecorded_attributes = frozenset({"lekcje", "wydarzenia_dnia", "godziny"})

    def __init__(self, coordinator, config_entry, slug, imie) -> None:
        super().__init__(coordinator, config_entry, slug, imie, "plan_dzis", "Plan lekcji dziś", "mdi:calendar-today")

    def _dzien(self) -> Dict[str, Any]:
        return self.coordinator.pobierz_dzien(dt_util.now().date().isoformat())

    @property
    def native_value(self) -> str:
        return self._dzien()["zakres"]

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        return {**self._dzien(), "godziny": self._godziny()}


class LibrusPlanJutroSensor(_LibrusPlanSensor):
    """Plan lekcji na najblizszy dzien nauki (jutro; w piatek poniedzialek)."""

    _unrecorded_attributes = frozenset({"lekcje", "wydarzenia_dnia", "godziny"})

    def __init__(self, coordinator, config_entry, slug, imie) -> None:
        super().__init__(coordinator, config_entry, slug, imie, "plan_jutro", "Plan lekcji jutro", "mdi:calendar-arrow-right")

    def _dzien(self) -> Dict[str, Any]:
        return self.coordinator.pobierz_dzien(self._iso_jutro(dt_util.now().date()))

    @property
    def native_value(self) -> str:
        return self._dzien()["zakres"]

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        dzis = dt_util.now().date()
        dzien = self._dzien()
        return {
            **dzien,
            "godziny": self._godziny(),
            "czy_jutro": dzien["data"] == (dzis + timedelta(days=1)).isoformat(),
        }


class LibrusNastepnaLekcjaSensor(_LibrusPlanSensor):
    """Trwajaca albo najblizsza dzisiejsza lekcja (liczone na biezaco)."""

    _tick_co_minute = True

    def __init__(self, coordinator, config_entry, slug, imie) -> None:
        super().__init__(coordinator, config_entry, slug, imie, "nastepna_lekcja", "Następna lekcja", "mdi:clock-start")

    def _lekcja(self) -> tuple:
        """Zwroc (lekcja, trwa) albo (None, tekst stanu gdy brak lekcji)."""
        teraz = dt_util.now()
        dzien = self.coordinator.pobierz_dzien(teraz.date().isoformat())
        aktywne = [l for l in dzien["lekcje"] if not l.get("odwolana")]
        if not aktywne:
            return None, "Brak lekcji"
        godz = teraz.strftime("%H:%M")
        for l in aktywne:
            if l["do"] > godz:
                return l, l["od"] <= godz
        return None, "Koniec lekcji"

    @property
    def native_value(self) -> str:
        lekcja, trwa = self._lekcja()
        return lekcja["przedmiot"] if lekcja else trwa

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        lekcja, trwa = self._lekcja()
        if not lekcja:
            return {}
        return {
            "numer": lekcja["numer"],
            "od": lekcja["od"],
            "do": lekcja["do"],
            "sala": lekcja["sala"],
            "nauczyciel": lekcja["nauczyciel"],
            "sprawdzian": lekcja.get("sprawdzian", False),
            "zastepstwo": lekcja.get("zastepstwo", False),
            "trwa": trwa,
        }


class LibrusPlanTygodniaSensor(_LibrusPlanSensor):
    """Plan tygodnia: domyslnie najblizszy tydzien nauki (od piatku po lekcjach nastepny)."""

    _unrecorded_attributes = frozenset({"dni", "godziny"})

    def __init__(self, coordinator, config_entry, slug, imie) -> None:
        super().__init__(coordinator, config_entry, slug, imie, "plan_tygodnia", "Plan tygodnia", "mdi:calendar-week")

    def _tydzien(self) -> Dict[str, Any]:
        teraz = dt_util.now()
        dane = self.coordinator.data or {}
        poczatek = wybierz_tydzien(teraz, self._plan_dni())
        tydzien = zbuduj_tydzien(dane.get("plan_scalony", {}), self._godziny(), poczatek)
        tydzien["nieaktualne"] = self.coordinator._plan_blad or poczatek.isoformat() in (
            (dane.get("plan") or {}).get("braki", [])
        )
        return tydzien

    @property
    def native_value(self) -> str:
        t = self._tydzien()
        od, do = parse_iso(t["tydzien_od"]), parse_iso(t["tydzien_do"])
        return f"{od:%d.%m}–{do:%d.%m}"

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        return {
            **self._tydzien(),
            "entry_id": self._config_entry.entry_id,
            "tryb": "auto",
            "wersja_integracji": VERSION,
        }


class LibrusDoZrobieniaJutroSensor(_LibrusPlanSensor):
    """Zadania, sprawdziany i przedmioty do spakowania na najblizszy dzien nauki."""

    _unrecorded_attributes = frozenset({"zadania", "sprawdziany", "przedmioty_do_spakowania"})

    def __init__(self, coordinator, config_entry, slug, imie) -> None:
        super().__init__(coordinator, config_entry, slug, imie, "do_zrobienia_jutro", "Do zrobienia na jutro", "mdi:bag-personal")

    def _dane(self) -> Dict[str, Any]:
        iso = self._iso_jutro(dt_util.now().date())
        zadania = odswiez_pilnosc(
            (self.coordinator.data or {}).get("zadania_norm", []), dt_util.now().date()
        )
        dzien = self.coordinator.pobierz_dzien(iso)
        wynik = do_zrobienia(dzien, zadania, iso)
        wynik["dzien"] = dzien.get("dzien", "")
        return wynik

    @property
    def native_value(self) -> int:
        d = self._dane()
        return len(d["zadania"]) + len(d["sprawdziany"])

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        return self._dane()


class LibrusZadaniaOtwarteSensor(_LibrusPlanSensor):
    """Zadania domowe do zrobienia (od dzisiaj) z pilnoscia; zalegle osobno."""

    _unrecorded_attributes = frozenset({"zadania", "po_terminie"})

    def __init__(self, coordinator, config_entry, slug, imie) -> None:
        super().__init__(coordinator, config_entry, slug, imie, "zadania_otwarte", "Zadania otwarte", "mdi:clipboard-text-clock")

    def _dane(self) -> Dict[str, Any]:
        zadania = odswiez_pilnosc(
            (self.coordinator.data or {}).get("zadania_norm", []), dt_util.now().date()
        )
        return podsumuj_otwarte(zadania)

    @property
    def native_value(self) -> int:
        return len(self._dane()["zadania"])

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        return {
            **self._dane(),
            "aktualne": (self.coordinator.data or {}).get("zadania_aktualne", True),
        }
