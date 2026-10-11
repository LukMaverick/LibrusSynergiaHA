"""The Librus APIX integration."""

import asyncio
import logging
import traceback
from datetime import date, datetime, timedelta
from typing import Dict, Any, Optional

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
)
from homeassistant.exceptions import ServiceValidationError
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers import config_validation as cv
from homeassistant.util import dt as dt_util

from librus_apix.client import Client, new_client
from librus_apix.exceptions import ParseError, TokenError

from .const import (
    DOMAIN,
    SCAN_INTERVAL,
    ZADANIA_NAPRZOD_DNI,
    ZADANIA_WSTECZ_DNI,
)
from .karta import async_register_frontend
from .plan import normalizuj_tydzien, poniedzialek

_LOGGER = logging.getLogger(__name__)


def _current_semester() -> int:
    """Zwroc numer biezacego semestru (1 lub 2) wg polskiego roku szkolnego.

    Semestr 1: wrzesien (9) - styczen (1)
    Semestr 2: luty (2) - czerwiec (6)
    Lipiec-sierpien to wakacje - zwracamy 2 (ostatni semestr roku).
    """
    m = date.today().month
    return 1 if m >= 9 else 2

PLATFORMS = ["sensor"]

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

                # Process all grades
                all_grades = []

                # Process numeric grades (only current semester)
                for subject_grades in numeric_grades:
                    for subject, grades_list in subject_grades.items():
                        for grade in grades_list:
                            if grade.semester != current_sem:
                                continue
                            all_grades.append({
                                'subject': subject,
                                'grade': grade.grade,
                                'date': grade.date,
                                'category': grade.category,
                                'teacher': getattr(grade, 'teacher', ''),
                                'semester': grade.semester,
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
                                all_grades.append({
                                    'subject': subject,
                                    'grade': desc_grade.grade,
                                    'date': desc_grade.date,
                                    'category': getattr(desc_grade, 'desc', '').split('\n')[0] if hasattr(desc_grade, 'desc') else '',
                                    'teacher': getattr(desc_grade, 'teacher', ''),
                                    'semester': desc_grade.semester,
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

    async def async_get_homework(self, od: Optional[date] = None, do: Optional[date] = None):
        """Get homework assignments from Librus (default: 7 days back to 30 days ahead)."""
        today = dt_util.now().date()
        od = od or today - timedelta(days=ZADANIA_WSTECZ_DNI)
        do = do or today + timedelta(days=ZADANIA_NAPRZOD_DNI)
        for attempt in range(2):
            try:
                if not self._client or not self._token:
                    if not await self.async_authenticate():
                        return None

                from librus_apix.homework import get_homework

                loop = asyncio.get_running_loop()
                return await loop.run_in_executor(
                    None,
                    get_homework,
                    self._client,
                    od.strftime("%Y-%m-%d"),
                    do.strftime("%Y-%m-%d"),
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
            except ParseError as ex:
                # Biblioteka nie odroznia pustej tabeli od zmiany HTML - koordynator zachowa
                # poprzednie dane, a po 24 h zalozy brak zadan
                _LOGGER.debug("Homework ParseError: %s", ex)
                return None
            except Exception as ex:
                _LOGGER.error(
                    "Failed to get homework (attempt %d/2): %s\n%s",
                    attempt + 1, ex, traceback.format_exc(),
                )
                self._reset_auth()
                if attempt == 1:
                    return None

    async def async_get_homework_detail(self, href: str):
        """Get homework details (label -> value) or None on failure."""
        for attempt in range(2):
            try:
                if not self._client or not self._token:
                    if not await self.async_authenticate():
                        return None

                from librus_apix.homework import homework_detail

                loop = asyncio.get_running_loop()
                return await loop.run_in_executor(
                    None, homework_detail, self._client, href
                )

            except TokenError:
                self._reset_auth()
                if attempt == 1:
                    return None
            except Exception as ex:
                _LOGGER.debug("Failed to get homework detail %s: %s", href, ex)
                return None

    async def async_get_schedule(self, od: Optional[date] = None, do: Optional[date] = None):
        """Get calendar events from Librus.

        Domyslnie: od poniedzialku biezacego tygodnia do konca nastepnego miesiaca.
        Miesiac bez zdarzen (ParseError z biblioteki) traktujemy jako pusty.
        """
        today = dt_util.now().date()
        od = od or poniedzialek(today)
        if do is None:
            nast = (today.replace(day=1) + timedelta(days=32)).replace(day=1)
            do = (nast.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)

        miesiace = []
        cur = od.replace(day=1)
        while cur <= do:
            miesiace.append((cur.year, cur.month))
            cur = (cur.replace(day=28) + timedelta(days=4)).replace(day=1)

        for attempt in range(2):
            try:
                if not self._client or not self._token:
                    if not await self.async_authenticate():
                        return None

                from librus_apix.schedule import get_schedule
                from librus_apix.exceptions import ParseError

                loop = asyncio.get_running_loop()

                def _fetch_months():
                    events = []
                    for year, month in miesiace:
                        try:
                            monthly = get_schedule(self._client, str(month).zfill(2), str(year))
                        except ParseError:
                            continue
                        for day_num, day_events in monthly.items():
                            event_date = date(year, month, int(day_num))
                            if event_date < od or event_date > do:
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

                return await loop.run_in_executor(None, _fetch_months)

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

    async def async_get_timetable(self, start: Optional[date] = None, weeks: int = 2):
        """Get the lesson plan for `weeks` weeks from the Monday of `start`'s week.

        Zwraca {"dni": {iso: [lekcje]}, "godziny": {...}, "braki": [poniedzialki]} albo None,
        gdy nie udalo sie pobrac zadnego tygodnia. Tydzien bez planu (ParseError, np. ferie)
        to puste dni, a nie blad.
        """
        start = poniedzialek(start or dt_util.now().date())
        for attempt in range(2):
            try:
                if not self._client or not self._token:
                    if not await self.async_authenticate():
                        return None

                from librus_apix.timetable import get_timetable
                from librus_apix.exceptions import ParseError

                loop = asyncio.get_running_loop()

                def _fetch_weeks():
                    dni, godziny, braki = {}, {}, []
                    for i in range(weeks):
                        monday = start + timedelta(weeks=i)
                        try:
                            tydzien = get_timetable(
                                self._client, datetime(monday.year, monday.month, monday.day)
                            )
                            znormalizowany = normalizuj_tydzien(tydzien)
                            dni.update(znormalizowany["dni"])
                            godziny.update(znormalizowany["godziny"])
                        except ParseError:
                            for d in range(7):
                                dni.setdefault((monday + timedelta(days=d)).isoformat(), [])
                        except TokenError:
                            raise
                        except Exception as ex:
                            _LOGGER.warning("Nie udalo sie pobrac planu tygodnia %s: %s", monday, ex)
                            braki.append(monday.isoformat())
                    return {"dni": dni, "godziny": godziny, "braki": braki}

                wynik = await loop.run_in_executor(None, _fetch_weeks)
                if len(wynik["braki"]) >= weeks:
                    return None
                return wynik

            except TokenError:
                _LOGGER.warning(
                    "Token expired fetching timetable (attempt %d/2), re-authenticating...",
                    attempt + 1,
                )
                self._reset_auth()
                if attempt == 1:
                    _LOGGER.error("Failed to get timetable after re-authentication.")
                    return None
            except Exception as ex:
                _LOGGER.error(
                    "Failed to get timetable (attempt %d/2): %s\n%s",
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


SERVICE_POBIERZ_TYDZIEN = "pobierz_tydzien"
POBIERZ_TYDZIEN_SCHEMA = vol.Schema(
    {
        vol.Required("entry_id"): cv.string,
        vol.Optional("poniedzialek"): cv.date,
    }
)


async def _async_register_services(hass: HomeAssistant) -> None:
    """Zarejestruj usluge pobierz_tydzien (raz dla calego HA)."""
    if hass.services.has_service(DOMAIN, SERVICE_POBIERZ_TYDZIEN):
        return

    async def _handle_pobierz_tydzien(call: ServiceCall) -> ServiceResponse:
        dane = hass.data.get(DOMAIN, {}).get(call.data["entry_id"])
        coordinator = dane.get("coordinator") if isinstance(dane, dict) else None
        if coordinator is None:
            raise ServiceValidationError(
                f"Nieznany wpis Librus: {call.data['entry_id']}"
            )
        return await coordinator.async_pobierz_tydzien(call.data.get("poniedzialek"))

    hass.services.async_register(
        DOMAIN,
        SERVICE_POBIERZ_TYDZIEN,
        _handle_pobierz_tydzien,
        schema=POBIERZ_TYDZIEN_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )


async def async_setup(hass: HomeAssistant, config: Dict[str, Any]) -> bool:
    """Set up the Librus APIX component."""
    hass.data.setdefault(DOMAIN, {})

    # Karta frontendowa i usluga nie moga blokowac reszty integracji
    try:
        await async_register_frontend(hass)
    except Exception:  # noqa: BLE001
        _LOGGER.warning(
            "Nie udalo sie zarejestrowac karty librus-card; dodaj zasob recznie (patrz README): %s",
            traceback.format_exc(),
        )
    await _async_register_services(hass)

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

    hass.data.setdefault(DOMAIN, {})
    # Koordynator uzupelnia sensor.py (potrzebny usludze pobierz_tydzien)
    hass.data[DOMAIN][entry.entry_id] = {"client": client, "coordinator": None}

    # Setup platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
