"""The Librus APIX integration."""

import asyncio
import logging
import traceback
from datetime import date
from typing import Dict, Any

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers import config_validation as cv

from librus_apix.client import Client, new_client
from librus_apix.exceptions import TokenError

from .const import (
    ATTR_PUSH,
    ATTR_TYP,
    ATTR_URL,
    CONF_SMS_HEADERS,
    CONF_SMS_METHOD,
    CONF_SMS_TEKST_OCENY,
    CONF_SMS_TEKST_UWAGI,
    CONF_SMS_VERIFY_SSL,
    DEFAULT_SMS_METHOD,
    DEFAULT_SMS_TEKST_OCENY,
    DEFAULT_SMS_TEKST_UWAGI,
    DEFAULT_SMS_VERIFY_SSL,
    DOMAIN,
    SCAN_INTERVAL,
    SERVICE_WYSLIJ_SMS,
    TYP_OCENA,
    TYP_UWAGA,
)
from .coordinator import LibrusDataUpdateCoordinator
from .sms import async_powiadom, async_wyslij_na_adresy, parsuj_naglowki, zbuduj_tekst

_LOGGER = logging.getLogger(__name__)


def _opis_na_slownik(desc: str) -> Dict[str, str]:
    """Zamien opis oceny z tooltipa Librusa ("Klucz: wartosc" w liniach) na slownik."""
    wynik: Dict[str, str] = {}
    for linia in (desc or "").splitlines():
        if ": " in linia:
            klucz, wartosc = linia.split(": ", 1)
            wynik[klucz.strip()] = wartosc.strip()
    return wynik


def _current_semester() -> int:
    """Zwroc numer biezacego semestru (1 lub 2) wg polskiego roku szkolnego.

    Semestr 1: wrzesien (9) - styczen (1)
    Semestr 2: luty (2) - czerwiec (6)
    Lipiec-sierpien to wakacje - zwracamy 2 (ostatni semestr roku).
    """
    m = date.today().month
    return 1 if m >= 9 else 2

PLATFORMS = ["sensor", "button"]

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_USERNAME): cv.string,
                vol.Required(CONF_PASSWORD): cv.string,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


class LibrusApiClient:
    """Class to interface with the Librus API."""

    def __init__(self, username: str, password: str):
        """Initialize the client."""
        self.username = username
        self.password = password
        self._client: Client = None
        self._token = None
        self._auth_lock = asyncio.Lock()
        # Oficjalne srednie z Librusa: {przedmiot: {semestr: srednia}} (aktualizowane przy pobraniu ocen)
        self.averages: Dict[str, Dict[int, Any]] = {}

    def _reset_auth(self) -> None:
        """Reset authentication state to force re-authentication on next call."""
        self._client = None
        self._token = None

    async def async_authenticate(self):
        """Authenticate with Librus API."""
        async with self._auth_lock:
            try:
                loop = asyncio.get_running_loop()
                self._client = await loop.run_in_executor(None, new_client)
                self._token = await loop.run_in_executor(
                    None, self._client.get_token, self.username, self.password
                )
                _LOGGER.debug("Authentication successful for %s", self.username)
                return True
            except Exception as ex:
                _LOGGER.error("Authentication failed: %s\n%s", ex, traceback.format_exc())
                self._reset_auth()
                return False

    async def async_get_grades(self):
        """Get grades from Librus."""
        for attempt in range(2):
            try:
                if not self._client or not self._token:
                    if not await self.async_authenticate():
                        return None
                client = self._client

                from librus_apix.grades import get_grades

                loop = asyncio.get_running_loop()
                numeric_grades, average_grades, descriptive_grades = await loop.run_in_executor(
                    None, get_grades, client, "all"
                )

                current_sem = _current_semester()
                _LOGGER.debug("Filtrowanie ocen dla semestru %d", current_sem)

                # Oficjalne srednie Librusa (Gpa) per przedmiot/semestr
                try:
                    srednie: Dict[str, Dict[int, Any]] = {}
                    for subject, gpa_list in (average_grades or {}).items():
                        for gpa in gpa_list:
                            srednie.setdefault(subject, {})[getattr(gpa, "semester", 0)] = getattr(gpa, "gpa", None)
                    self.averages = srednie
                except Exception:  # pylint: disable=broad-except
                    _LOGGER.debug("Nie udalo sie odczytac srednich Librusa", exc_info=True)

                # Process all grades
                all_grades = []

                # Process numeric grades (only current semester)
                for subject_grades in numeric_grades:
                    for subject, grades_list in subject_grades.items():
                        for grade in grades_list:
                            if grade.semester != current_sem:
                                continue
                            opis = _opis_na_slownik(getattr(grade, 'desc', ''))
                            all_grades.append({
                                'subject': subject,
                                'grade': grade.grade,
                                'date': grade.date,
                                'category': grade.category,
                                'teacher': getattr(grade, 'teacher', ''),
                                'semester': grade.semester,
                                'weight': getattr(grade, 'weight', 0),
                                'counts': getattr(grade, 'counts', True),
                                'comment': opis.get('Komentarz', ''),
                                'type': 'numeric'
                            })

                # Process descriptive grades (only current semester, many are actually numeric)
                for subject_grades in descriptive_grades:
                    for subject, grades_list in subject_grades.items():
                        for desc_grade in grades_list:
                            if desc_grade.semester != current_sem:
                                continue
                            grade_val = desc_grade.grade.strip()
                            if grade_val and (grade_val.replace('+', '').replace('-', '').isdigit() or
                                            grade_val in ['1', '2', '3', '4', '5', '6', '1+', '1-', '2+', '2-',
                                                         '3+', '3-', '4+', '4-', '5+', '5-', '6+', '6-']):
                                opis = _opis_na_slownik(getattr(desc_grade, 'desc', ''))
                                try:
                                    waga = int(opis.get('Waga', 1))
                                except ValueError:
                                    waga = 1
                                all_grades.append({
                                    'subject': subject,
                                    'grade': desc_grade.grade,
                                    'date': desc_grade.date,
                                    'category': opis.get('Kategoria') or (getattr(desc_grade, 'desc', '').split('\n')[0] if hasattr(desc_grade, 'desc') else ''),
                                    'teacher': getattr(desc_grade, 'teacher', ''),
                                    'semester': desc_grade.semester,
                                    'weight': waga,
                                    'counts': opis.get('Licz do średniej', 'tak').lower() == 'tak',
                                    'comment': opis.get('Komentarz', ''),
                                    'type': 'descriptive'
                                })

                return all_grades

            except TokenError as ex:
                _LOGGER.warning(
                    "Token expired fetching grades (attempt %d/2), re-authenticating...",
                    attempt + 1,
                )
                self._reset_auth()
                if attempt == 1:
                    _LOGGER.error("Failed to get grades after re-authentication.")
                    return None
            except Exception as ex:
                _LOGGER.error(
                    "Failed to get grades (attempt %d/2): %s\n%s",
                    attempt + 1, ex, traceback.format_exc(),
                )
                self._reset_auth()
                if attempt == 1:
                    return None

    async def async_get_messages(self, count: int = 10):
        """Get latest messages from Librus (subject and sender only, no content fetch to avoid marking as read)."""
        for attempt in range(2):
            try:
                if not self._client or not self._token:
                    if not await self.async_authenticate():
                        return None
                client = self._client

                from librus_apix.messages import get_received

                loop = asyncio.get_running_loop()
                messages = await loop.run_in_executor(None, get_received, client, 0)
                messages = messages[:count] if messages else []

                result = [
                    {
                        "author": msg.author,
                        "title": msg.title,
                        "date": msg.date,
                        "href": msg.href,
                        "unread": msg.unread,
                        "has_attachment": msg.has_attachment,
                    }
                    for msg in messages
                ]

                return result

            except TokenError as ex:
                _LOGGER.warning(
                    "Token expired fetching messages (attempt %d/2), re-authenticating...",
                    attempt + 1,
                )
                self._reset_auth()
                if attempt == 1:
                    _LOGGER.error("Failed to get messages after re-authentication.")
                    return None
            except Exception as ex:
                _LOGGER.error(
                    "Failed to get messages (attempt %d/2): %s\n%s",
                    attempt + 1, ex, traceback.format_exc(),
                )
                self._reset_auth()
                if attempt == 1:
                    return None

    async def async_get_homework(self):
        """Get upcoming homework assignments from Librus (next 30 days)."""
        for attempt in range(2):
            try:
                if not self._client or not self._token:
                    if not await self.async_authenticate():
                        return None

                from librus_apix.homework import get_homework
                from datetime import date as _date, timedelta

                today = _date.today()
                date_from = today.strftime("%Y-%m-%d")
                date_to = (today + timedelta(days=30)).strftime("%Y-%m-%d")

                loop = asyncio.get_running_loop()
                return await loop.run_in_executor(
                    None, get_homework, self._client, date_from, date_to
                )

            except TokenError:
                _LOGGER.warning(
                    "Token expired fetching homework (attempt %d/2), re-authenticating...",
                    attempt + 1,
                )
                self._reset_auth()
                if attempt == 1:
                    _LOGGER.error("Failed to get homework after re-authentication.")
                    return None
            except Exception as ex:
                _LOGGER.error(
                    "Failed to get homework (attempt %d/2): %s\n%s",
                    attempt + 1, ex, traceback.format_exc(),
                )
                self._reset_auth()
                if attempt == 1:
                    return None

    async def async_get_schedule(self):
        """Get upcoming calendar events from Librus (current + next month, filtered to future dates)."""
        for attempt in range(2):
            try:
                if not self._client or not self._token:
                    if not await self.async_authenticate():
                        return None

                from librus_apix.schedule import get_schedule
                from datetime import date as _date
                import calendar

                today = _date.today()
                loop = asyncio.get_running_loop()

                def _fetch_two_months():
                    events = []
                    for year, month in [
                        (today.year, today.month),
                        (
                            today.year + 1 if today.month == 12 else today.year,
                            1 if today.month == 12 else today.month + 1,
                        ),
                    ]:
                        monthly = get_schedule(self._client, str(month).zfill(2), str(year))
                        for day_num, day_events in monthly.items():
                            event_date = _date(year, month, int(day_num))
                            if event_date < today:
                                continue
                            for ev in day_events:
                                events.append({
                                    "data": event_date.strftime("%Y-%m-%d"),
                                    "tydzien": event_date.strftime("%A"),
                                    "tytul": ev.title,
                                    "przedmiot": ev.subject,
                                    "godzina": ev.hour,
                                    "numer_lekcji": ev.number,
                                    "szczegoly": ev.data,
                                    "href": ev.href,
                                })
                    return sorted(events, key=lambda e: e["data"])

                return await loop.run_in_executor(None, _fetch_two_months)

            except TokenError:
                _LOGGER.warning(
                    "Token expired fetching schedule (attempt %d/2), re-authenticating...",
                    attempt + 1,
                )
                self._reset_auth()
                if attempt == 1:
                    _LOGGER.error("Failed to get schedule after re-authentication.")
                    return None
            except Exception as ex:
                _LOGGER.error(
                    "Failed to get schedule (attempt %d/2): %s\n%s",
                    attempt + 1, ex, traceback.format_exc(),
                )
                self._reset_auth()
                if attempt == 1:
                    return None

    async def async_get_uwagi(self):
        """Get behaviour notes (uwagi) from Librus. Returns list of dicts or None on error."""
        for attempt in range(2):
            try:
                if not self._client or not self._token:
                    if not await self.async_authenticate():
                        return None

                from .uwagi import pobierz_uwagi

                loop = asyncio.get_running_loop()
                return await loop.run_in_executor(None, pobierz_uwagi, self._client)

            except TokenError:
                _LOGGER.warning(
                    "Token expired fetching uwagi (attempt %d/2), re-authenticating...",
                    attempt + 1,
                )
                self._reset_auth()
                if attempt == 1:
                    _LOGGER.error("Failed to get uwagi after re-authentication.")
                    return None
            except Exception as ex:
                _LOGGER.error(
                    "Failed to get uwagi (attempt %d/2): %s\n%s",
                    attempt + 1, ex, traceback.format_exc(),
                )
                self._reset_auth()
                if attempt == 1:
                    return None

    async def async_get_student_information(self):
        """Get student information from Librus."""
        try:
            if not self._client or not self._token:
                if not await self.async_authenticate():
                    return None

            from librus_apix.student_information import get_student_information

            loop = asyncio.get_running_loop()
            return await loop.run_in_executor(None, get_student_information, self._client)

        except Exception as ex:
            _LOGGER.error(
                "Failed to get student information: %s\n%s", ex, traceback.format_exc()
            )
            self._reset_auth()
            return None


async def async_setup(hass: HomeAssistant, config: Dict[str, Any]) -> bool:
    """Set up the Librus APIX component."""
    hass.data.setdefault(DOMAIN, {})
    
    if DOMAIN in config:
        username = config[DOMAIN][CONF_USERNAME]
        password = config[DOMAIN][CONF_PASSWORD]
        
        client = LibrusApiClient(username, password)
        hass.data[DOMAIN]["client"] = client
        
        # Test authentication
        if not await client.async_authenticate():
            _LOGGER.error("Failed to authenticate")
            return False

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Librus APIX from a config entry."""
    username = entry.data[CONF_USERNAME]
    password = entry.data[CONF_PASSWORD]
    
    client = LibrusApiClient(username, password)
    
    # Test authentication
    if not await client.async_authenticate():
        _LOGGER.error("Failed to authenticate")
        return False
    
    # Koordynator wspolny dla wszystkich platform (sensor, button)
    coordinator = LibrusDataUpdateCoordinator(hass, client, entry)
    await coordinator.async_load_seen()
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {"client": client, "coordinator": coordinator}

    # Setup platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Zmiana opcji (Konfiguruj) -> przeladuj wpis, zeby nowe ustawienia zadzialaly od razu
    entry.async_on_unload(entry.add_update_listener(_async_options_updated))

    _async_register_services(hass)

    return True


async def _async_options_updated(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Przeladuj integracje po zmianie opcji."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)

    # Ostatni wpis usuniety -> wyrejestruj akcje
    if not [e for e in hass.config_entries.async_entries(DOMAIN) if e.entry_id in hass.data[DOMAIN]]:
        if hass.services.has_service(DOMAIN, SERVICE_WYSLIJ_SMS):
            hass.services.async_remove(DOMAIN, SERVICE_WYSLIJ_SMS)

    return unload_ok


# ---------------------------------------------------------------- akcja HA

SERVICE_WYSLIJ_SMS_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_TYP, default=TYP_OCENA): vol.In([TYP_OCENA, TYP_UWAGA]),
        vol.Optional("ocena", default=""): cv.string,
        vol.Optional("przedmiot", default=""): cv.string,
        vol.Optional("tresc", default=""): cv.string,
        vol.Optional("rodzaj", default=""): cv.string,
        vol.Optional("kategoria", default=""): cv.string,
        vol.Optional("nauczyciel", default=""): cv.string,
        vol.Optional("data", default=""): cv.string,
        vol.Optional("waga", default=""): cv.string,
        vol.Optional("komentarz", default=""): cv.string,
        vol.Optional("srednia", default=""): cv.string,
        vol.Optional("uczen"): cv.string,
        vol.Optional("tekst"): cv.string,
        vol.Optional(ATTR_URL): cv.string,
        vol.Optional(ATTR_PUSH, default=False): cv.boolean,
    }
)


@callback
def _async_register_services(hass: HomeAssistant) -> None:
    """Zarejestruj akcje librus_apix.wyslij_sms (raz)."""
    if hass.services.has_service(DOMAIN, SERVICE_WYSLIJ_SMS):
        return

    async def _handle_wyslij_sms(call: ServiceCall) -> None:
        dane: Dict[str, Any] = dict(call.data)
        typ = dane.pop(ATTR_TYP, TYP_OCENA)
        url_override = dane.pop(ATTR_URL, None)
        tekst_override = dane.pop("tekst", None)
        z_push = dane.pop(ATTR_PUSH, False)

        wpisy = [
            (entry, hass.data[DOMAIN].get(entry.entry_id) or {})
            for entry in hass.config_entries.async_entries(DOMAIN)
            if entry.entry_id in hass.data[DOMAIN]
        ]

        # Adres podany bezposrednio w akcji - wyslij od razu (SSL/metoda/tekst z pierwszego wpisu)
        if url_override:
            verify_ssl = DEFAULT_SMS_VERIFY_SSL
            metoda = DEFAULT_SMS_METHOD
            naglowki: Dict[str, str] = {}
            szablon_tekstu = DEFAULT_SMS_TEKST_OCENY if typ == TYP_OCENA else DEFAULT_SMS_TEKST_UWAGI
            if wpisy:
                entry, dane_wpisu = wpisy[0]
                verify_ssl = entry.options.get(CONF_SMS_VERIFY_SSL, DEFAULT_SMS_VERIFY_SSL)
                metoda = entry.options.get(CONF_SMS_METHOD, DEFAULT_SMS_METHOD)
                naglowki = parsuj_naglowki(entry.options.get(CONF_SMS_HEADERS, ""))
                szablon_tekstu = entry.options.get(
                    CONF_SMS_TEKST_OCENY if typ == TYP_OCENA else CONF_SMS_TEKST_UWAGI,
                    szablon_tekstu,
                )
                dane.setdefault("uczen", _nazwa_ucznia(dane_wpisu))
            dane["typ"] = typ
            dane["tekst"] = tekst_override or zbuduj_tekst(szablon_tekstu, dane)
            await async_wyslij_na_adresy(hass, url_override, dane, verify_ssl, metoda, naglowki)
            return

        wyslano = 0
        for entry, dane_wpisu in wpisy:
            dane_e = dict(dane)
            dane_e.setdefault("uczen", _nazwa_ucznia(dane_wpisu))
            wynik = await async_powiadom(
                hass, entry.options, typ, dane_e, sms=True, push=z_push, tekst=tekst_override
            )
            wyslano += wynik["sms"] + wynik["push"]

        if wyslano == 0:
            _LOGGER.warning(
                "librus_apix.wyslij_sms: nic nie wyslano - sprawdz, czy bramka SMS jest wlaczona "
                "i ma adresy dla typu '%s' (Ustawienia -> Integracje -> Librus -> Konfiguruj)",
                typ,
            )

    hass.services.async_register(
        DOMAIN, SERVICE_WYSLIJ_SMS, _handle_wyslij_sms, schema=SERVICE_WYSLIJ_SMS_SCHEMA
    )


def _nazwa_ucznia(dane_wpisu: Dict[str, Any]) -> str:
    """Imie i nazwisko ucznia z koordynatora (jesli juz pobrane)."""
    coordinator = dane_wpisu.get("coordinator")
    data = getattr(coordinator, "data", None) or {}
    info = data.get("student_info")
    return getattr(info, "name", "") or ""