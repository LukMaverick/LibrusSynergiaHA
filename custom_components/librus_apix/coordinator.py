"""Koordynator pobierania danych z Librusa + wykrywanie nowosci (zdarzenia HA, SMS, push)."""

import logging
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_SCAN_INTERVAL,
    CONF_SCAN_INTERVAL_SZKOLA,
    CONF_SZKOLA_DNI_ROBOCZE,
    CONF_SZKOLA_DO,
    CONF_SZKOLA_OD,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL_SZKOLA,
    DEFAULT_SZKOLA_DNI_ROBOCZE,
    DEFAULT_SZKOLA_DO,
    DEFAULT_SZKOLA_OD,
    DOMAIN,
    MIN_SCAN_INTERVAL,
    SCAN_INTERVAL,
    STORAGE_KEY,
    STORAGE_VERSION,
    TYP_OCENA,
    TYP_UWAGA,
)
from .sms import async_powiadom

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


EVENT_NOWA_WIADOMOSC = f"{DOMAIN}_nowa_wiadomosc"
EVENT_NOWA_OCENA = f"{DOMAIN}_nowa_ocena"
EVENT_NOWE_ZADANIE = f"{DOMAIN}_nowe_zadanie"
EVENT_NOWE_ZDARZENIE = f"{DOMAIN}_nowe_zdarzenie"
EVENT_NOWA_UWAGA = f"{DOMAIN}_nowa_uwaga"


def _godzina(tekst: Any, domyslna: str) -> timedelta:
    """'HH:MM[:SS]' -> timedelta od polnocy (bledny format -> domyslna)."""
    for wartosc in (tekst, domyslna):
        try:
            czesci = [int(x) for x in str(wartosc).split(":")]
            h, m = czesci[0], czesci[1] if len(czesci) > 1 else 0
            if 0 <= h <= 24 and 0 <= m < 60:
                return timedelta(hours=h, minutes=m)
        except (TypeError, ValueError, IndexError):
            continue
    return timedelta(hours=7)


def _minuty(wartosc: Any, domyslna: int) -> int:
    try:
        return max(int(float(wartosc)), MIN_SCAN_INTERVAL)
    except (TypeError, ValueError):
        return domyslna


def oblicz_interwal(opcje: Dict[str, Any], teraz: datetime) -> tuple:
    """Zwroc (interwal, tryb) dla chwili `teraz` (czas lokalny).

    W oknie szkolnym (np. 07:00-15:00, dni robocze) sprawdzamy czesciej; poza nim rzadziej,
    ale nie dalej niz do poczatku nastepnego okna szkolnego (zeby pierwsze sprawdzenie
    po nocy nie przesunelo sie w glab lekcji).
    """
    w_szkole_min = _minuty(opcje.get(CONF_SCAN_INTERVAL_SZKOLA), DEFAULT_SCAN_INTERVAL_SZKOLA)
    poza_min = _minuty(opcje.get(CONF_SCAN_INTERVAL), DEFAULT_SCAN_INTERVAL)
    od = _godzina(opcje.get(CONF_SZKOLA_OD), DEFAULT_SZKOLA_OD)
    do = _godzina(opcje.get(CONF_SZKOLA_DO), DEFAULT_SZKOLA_DO)
    tylko_robocze = opcje.get(CONF_SZKOLA_DNI_ROBOCZE, DEFAULT_SZKOLA_DNI_ROBOCZE)

    if od >= do:
        # okno wylaczone / bledne -> zawsze tryb "poza szkola"
        return timedelta(minutes=poza_min), "poza_szkola"

    def _dzien_szkolny(d: datetime) -> bool:
        return not tylko_robocze or d.weekday() < 5

    polnoc = teraz.replace(hour=0, minute=0, second=0, microsecond=0)
    od_dt, do_dt = polnoc + od, polnoc + do
    if _dzien_szkolny(teraz) and od_dt <= teraz < do_dt:
        return timedelta(minutes=w_szkole_min), "szkola"

    # poza szkola: znajdz poczatek najblizszego okna szkolnego (do 8 dni do przodu)
    nastepny_start: Optional[datetime] = None
    for dni in range(0, 8):
        kandydat = polnoc + timedelta(days=dni) + od
        if kandydat > teraz and _dzien_szkolny(kandydat):
            nastepny_start = kandydat
            break
    interwal = timedelta(minutes=poza_min)
    if nastepny_start is not None:
        do_startu = nastepny_start - teraz
        if timedelta(minutes=1) < do_startu < interwal:
            interwal = do_startu
    return interwal, "poza_szkola"


def _wartosc_oceny(grade_str: str) -> Optional[float]:
    """Zamien ocene tekstowa (np. '4+', '3-') na liczbe; None gdy nie jest liczba."""
    try:
        base = float(str(grade_str).strip()[0])
    except (ValueError, IndexError):
        return None
    if len(str(grade_str).strip()) > 1:
        if "+" in grade_str:
            base += 0.5
        elif "-" in grade_str:
            base -= 0.25
    return base


def _srednia_ocen(oceny: List[Dict]) -> Optional[float]:
    """Srednia wazona ocen (jak w Librusie): waga z oceny, pomijane oceny 'nie liczy do sredniej'.

    Gdy zadna ocena nie ma wagi > 0, liczona jest zwykla srednia arytmetyczna.
    """
    suma = 0.0
    suma_wag = 0.0
    wartosci: List[float] = []
    for g in oceny:
        if g.get("liczy_do_sredniej") is False:
            continue
        w = _wartosc_oceny(g.get("ocena", ""))
        if w is None:
            continue
        wartosci.append(w)
        try:
            waga = float(g.get("waga") or 0)
        except (TypeError, ValueError):
            waga = 0
        if waga > 0:
            suma += w * waga
            suma_wag += waga
    if suma_wag > 0:
        return round(suma / suma_wag, 2)
    return round(sum(wartosci) / len(wartosci), 2) if wartosci else None


def _data_z_tekstu(date_str: str) -> Optional[datetime]:
    """Sparsuj date/czas z tekstu Librusa (kilka formatow)."""
    if not date_str:
        return None
    for fmt in (
        "%d.%m.%Y %H:%M:%S",
        "%d.%m.%Y %H:%M",
        "%d.%m.%Y",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d",
    ):
        try:
            return datetime.strptime(date_str.strip(), fmt)
        except ValueError:
            continue
    return None


def _najnowszy(elementy: List[Dict], klucz_daty: str) -> Optional[Dict]:
    """Zwroc element o najpozniejszej dacie (przy remisie - ostatni na liscie)."""
    najnowszy: Optional[Dict] = None
    najnowsza_data: Optional[datetime] = None
    for el in elementy:
        d = _data_z_tekstu(str(el.get(klucz_daty, "")))
        if d is None:
            continue
        if najnowsza_data is None or d >= najnowsza_data:
            najnowsza_data = d
            najnowszy = el
    if najnowszy is None and elementy:
        return elementy[-1]
    return najnowszy


class LibrusDataUpdateCoordinator(DataUpdateCoordinator):
    """Klasa zarzadzajaca pobieraniem danych z Librus."""

    def __init__(
        self, hass: HomeAssistant, client: Any, config_entry: Optional[ConfigEntry] = None
    ) -> None:
        """Inicjalizacja koordynatora."""
        self.client = client
        self._entry = config_entry
        self._uczen: str = ""
        self._seen_message_hrefs: set = set()
        self._seen_grade_ids: set = set()
        self._seen_homework_ids: set = set()
        self._seen_schedule_ids: set = set()
        self._seen_uwagi_ids: set = set()
        self._ostatnia_nowa_ocena: Optional[Dict] = None
        self._ostatnia_nowa_wiadomosc: Optional[Dict] = None
        self._ostatnia_nowa_uwaga: Optional[Dict] = None
        self._srednie: Dict[str, Dict[str, Any]] = {}
        self._first_run: bool = True
        self._zmienione: bool = False

        # Magazyn HA (.storage/librus_apix.seen.<entry_id>) - pamiec "co juz widzielismy",
        # dzieki temu po restarcie HA nie gubimy nowych ocen i nie wysylamy duplikatow.
        self._store: Optional[Store] = (
            Store(hass, STORAGE_VERSION, f"{STORAGE_KEY}.{config_entry.entry_id}")
            if config_entry is not None
            else None
        )

        interwal = SCAN_INTERVAL
        self.tryb_sprawdzania: str = "poza_szkola"
        if config_entry is not None:
            interwal, self.tryb_sprawdzania = oblicz_interwal(dict(config_entry.options), dt_util.now())

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=interwal,
        )

    def _ustaw_interwal(self) -> None:
        """Dobierz interwal kolejnego sprawdzenia do pory dnia (szkola / poza szkola)."""
        if self._entry is None:
            return
        interwal, tryb = oblicz_interwal(dict(self._entry.options), dt_util.now())
        if interwal != self.update_interval or tryb != self.tryb_sprawdzania:
            _LOGGER.debug("Tryb sprawdzania: %s, nastepne za %s", tryb, interwal)
        self.update_interval = interwal
        self.tryb_sprawdzania = tryb

    # ------------------------------------------------------------ magazyn HA

    async def async_load_seen(self) -> None:
        """Wczytaj z magazynu HA liste juz widzianych elementow (po restarcie HA)."""
        if self._store is None:
            return
        try:
            dane = await self._store.async_load()
        except Exception as ex:  # pylint: disable=broad-except
            _LOGGER.warning("Nie udalo sie wczytac magazynu Librus: %s", ex)
            return
        if not dane:
            return
        self._seen_grade_ids = set(dane.get("oceny", []))
        self._seen_message_hrefs = set(dane.get("wiadomosci", []))
        self._seen_homework_ids = set(dane.get("zadania", []))
        self._seen_schedule_ids = set(dane.get("terminarz", []))
        self._seen_uwagi_ids = set(dane.get("uwagi", []))
        self._ostatnia_nowa_ocena = dane.get("ostatnia_nowa_ocena")
        self._ostatnia_nowa_wiadomosc = dane.get("ostatnia_nowa_wiadomosc")
        self._ostatnia_nowa_uwaga = dane.get("ostatnia_nowa_uwaga")
        # Mamy historie - kolejne pobranie porownujemy z nia (nowosci z czasu, gdy HA nie dzialal, tez wyslemy)
        self._first_run = False
        _LOGGER.debug(
            "Wczytano magazyn: %d ocen, %d wiadomosci, %d uwag",
            len(self._seen_grade_ids), len(self._seen_message_hrefs), len(self._seen_uwagi_ids),
        )

    async def _async_save_seen(self) -> None:
        """Zapisz liste widzianych elementow do magazynu HA."""
        if self._store is None:
            return
        try:
            await self._store.async_save(
                {
                    "oceny": sorted(self._seen_grade_ids),
                    "wiadomosci": sorted(self._seen_message_hrefs),
                    "zadania": sorted(self._seen_homework_ids),
                    "terminarz": sorted(self._seen_schedule_ids),
                    "uwagi": sorted(self._seen_uwagi_ids),
                    "ostatnia_nowa_ocena": self._ostatnia_nowa_ocena,
                    "ostatnia_nowa_wiadomosc": self._ostatnia_nowa_wiadomosc,
                    "ostatnia_nowa_uwaga": self._ostatnia_nowa_uwaga,
                }
            )
        except Exception as ex:  # pylint: disable=broad-except
            _LOGGER.warning("Nie udalo sie zapisac magazynu Librus: %s", ex)

    @staticmethod
    def _id_oceny(grade: Dict) -> str:
        return f"{grade.get('subject','')}|{grade.get('date','')}|{grade.get('grade','')}|{grade.get('category','')}"

    @staticmethod
    def _id_zadania(zadanie: Dict) -> str:
        return f"{zadanie.get('przedmiot','')}|{zadanie.get('termin','')}|{zadanie.get('kategoria','')}"

    @staticmethod
    def _id_zdarzenia(zdarzenie: Dict) -> str:
        return f"{zdarzenie.get('data','')}|{zdarzenie.get('tytul','')}|{zdarzenie.get('przedmiot','')}"

    async def _async_update_data(self) -> Dict[str, Any]:
        """Pobierz aktualne dane z API Librus."""
        from datetime import date as _date
        current_sem = 1 if _date.today().month >= 9 else 2

        # Interwal kolejnego odswiezenia zalezy od pory dnia - ustawiamy przed pobraniem,
        # koordynator uzyje go planujac nastepne sprawdzenie.
        self._ustaw_interwal()

        try:
            student_info = await self.client.async_get_student_information()
            grades = await self.client.async_get_grades()
            messages = await self.client.async_get_messages(count=10)
            homework_raw = await self.client.async_get_homework()
            schedule_raw = await self.client.async_get_schedule()
            uwagi_raw = await self.client.async_get_uwagi()

            self._uczen = getattr(student_info, "name", "") or ""

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
                    "srednie": prev.get("srednie", {}),
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
                    "uwagi": (
                        uwagi_raw if uwagi_raw is not None else prev.get("uwagi", [])
                    ),
                    "ostatnia_nowa_ocena": prev.get("ostatnia_nowa_ocena"),
                    "ostatnia_nowa_wiadomosc": prev.get("ostatnia_nowa_wiadomosc"),
                    "ostatnia_nowa_uwaga": prev.get("ostatnia_nowa_uwaga"),
                    "semestr_biezacy": prev.get("semestr_biezacy", current_sem),
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
                    "waga": grade.get("weight", 0),
                    "liczy_do_sredniej": grade.get("counts", True),
                    "komentarz": grade.get("comment", ""),
                    "semestr": grade.get("semester"),
                    "jest_nowa": _jest_nowa(grade["date"]),
                })

            # Srednie: wyliczona (wazona) i oficjalna z Librusa (jesli klient ja udostepnia)
            srednie_librus = getattr(self.client, "averages", None)
            if not isinstance(srednie_librus, dict):
                srednie_librus = {}
            srednie: Dict[str, Dict[str, Any]] = {}
            for subject, lista in oceny_wg_przedmiotu.items():
                per_sem = srednie_librus.get(subject)
                librus = per_sem.get(current_sem) if isinstance(per_sem, dict) else None
                if librus is not None and not isinstance(librus, (int, float, str)):
                    librus = None
                srednie[subject] = {"wyliczona": _srednia_ocen(lista), "librus": librus}
            self._srednie = srednie

            wiadomosci = self._build_wiadomosci(messages)
            zadania = self._build_zadania(homework_raw)
            terminarz = schedule_raw if schedule_raw is not None else []
            uwagi = uwagi_raw if uwagi_raw is not None else (self.data or {}).get("uwagi", [])

            result = {
                "student_info": student_info,
                "tryb_sprawdzania": self.tryb_sprawdzania,
                "interwal_minuty": int(self.update_interval.total_seconds() // 60) if self.update_interval else None,
                "oceny": grades,
                "oceny_wg_przedmiotu": oceny_wg_przedmiotu,
                "srednie": srednie,
                "wiadomosci": wiadomosci,
                "zadania": zadania,
                "terminarz": terminarz,
                "uwagi": uwagi,
                "semestr_biezacy": current_sem,
            }

            # Pierwsze pobranie (brak historii w magazynie HA) - tylko zapamietaj stan,
            # nie wysylaj powiadomien. Kolejne pobrania (takze po restarcie HA) porownuja
            # z zapamietana lista i wysylaja zdarzenia/SMS tylko dla nowosci.
            self._zmienione = False
            if self._first_run:
                self._first_run = False
                self._zmienione = True
                for msg in wiadomosci:
                    self._seen_message_hrefs.add(msg["href"])
                for grade in grades:
                    self._seen_grade_ids.add(self._id_oceny(grade))
                for zadanie in zadania:
                    self._seen_homework_ids.add(self._id_zadania(zadanie))
                for zdarzenie in terminarz:
                    self._seen_schedule_ids.add(self._id_zdarzenia(zdarzenie))
                for uwaga in uwagi:
                    self._seen_uwagi_ids.add(uwaga["id"])
            else:
                self._fire_events(wiadomosci, grades)
                self._fire_homework_events(zadania)
                self._fire_schedule_events(terminarz)
                self._fire_uwagi_events(uwagi)

            if self._zmienione:
                await self._async_save_seen()

            # "Ostatnia nowa" ocena / wiadomosc / uwaga = ostatnio wykryta nowosc
            # (pamietana w magazynie HA); jesli jeszcze zadnej nie wykryto - najnowsza wg daty.
            result["ostatnia_nowa_ocena"] = self._ostatnia_nowa_ocena or self._ostatnia_ocena_z_listy(grades)
            result["ostatnia_nowa_uwaga"] = self._ostatnia_nowa_uwaga or _najnowszy(uwagi, "data")
            result["ostatnia_nowa_wiadomosc"] = self._ostatnia_nowa_wiadomosc or self._ostatnia_wiadomosc_z_listy(wiadomosci)

            return result

        except UpdateFailed:
            raise
        except Exception as err:
            raise UpdateFailed(f"Blad komunikacji z API: {err}") from err

    @staticmethod
    def _ostatnia_ocena_z_listy(grades: List[Dict]) -> Optional[Dict]:
        """Najnowsza ocena (wg daty) w formacie zdarzenia."""
        g = _najnowszy(grades, "date")
        if not g:
            return None
        return {
            "przedmiot": g.get("subject", ""),
            "ocena": g.get("grade", ""),
            "data": g.get("date", ""),
            "kategoria": g.get("category", ""),
            "nauczyciel": g.get("teacher", ""),
            "waga": g.get("weight", 0),
            "liczy_do_sredniej": g.get("counts", True),
            "komentarz": g.get("comment", ""),
        }

    @staticmethod
    def _ostatnia_wiadomosc_z_listy(messages: List[Dict]) -> Optional[Dict]:
        """Najnowsza wiadomosc (Librus zwraca od najnowszej)."""
        if not messages:
            return None
        m = messages[0]
        return {
            "nadawca": m.get("author", ""),
            "temat": m.get("title", ""),
            "data": m.get("date", ""),
            "nieprzeczytana": m.get("unread", False),
            "ma_zalacznik": m.get("has_attachment", False),
        }

    # ------------------------------------------------------------ SMS / push

    def _wyslij_sms(self, typ: str, dane: Dict[str, Any]) -> None:
        """Zaplanuj wysylke SMS/push przez kanaly skonfigurowane w opcjach integracji."""
        if self._entry is None:
            return
        dane = dict(dane)
        dane.setdefault("uczen", self._uczen)
        self.hass.async_create_task(
            async_powiadom(self.hass, self._entry.options, typ, dane)
        )

    # --------------------------------------------------------------- zdarzenia

    def _fire_events(self, messages: List[Dict], grades: List[Dict]) -> None:
        """Wyslij zdarzenia HA dla nowych wiadomosci i ocen."""
        for msg in messages:
            href = msg.get("href", "")
            if href and href not in self._seen_message_hrefs:
                self._seen_message_hrefs.add(href)
                self._zmienione = True
                _LOGGER.debug("Nowa wiadomosc: %s", msg.get("title"))
                dane = {
                    "nadawca": msg.get("author", ""),
                    "temat": msg.get("title", ""),
                    "data": msg.get("date", ""),
                    "nieprzeczytana": msg.get("unread", False),
                    "ma_zalacznik": msg.get("has_attachment", False),
                    "uczen": self._uczen,
                }
                self._ostatnia_nowa_wiadomosc = dane
                self.hass.bus.fire(EVENT_NOWA_WIADOMOSC, dane)

        for grade in grades:
            grade_id = self._id_oceny(grade)
            if grade_id not in self._seen_grade_ids:
                self._seen_grade_ids.add(grade_id)
                self._zmienione = True
                _LOGGER.debug("Nowa ocena: %s %s", grade["subject"], grade["grade"])
                srednia = (self._srednie.get(grade["subject"]) or {}).get("wyliczona")
                dane = {
                    "przedmiot": grade["subject"],
                    "ocena": grade["grade"],
                    "data": grade["date"],
                    "kategoria": grade["category"],
                    "nauczyciel": grade["teacher"],
                    "waga": grade.get("weight", 0),
                    "liczy_do_sredniej": grade.get("counts", True),
                    "komentarz": grade.get("comment", ""),
                    "srednia": "" if srednia is None else srednia,
                    "srednia_librus": (self._srednie.get(grade["subject"]) or {}).get("librus"),
                    "uczen": self._uczen,
                }
                self._ostatnia_nowa_ocena = dane
                self.hass.bus.fire(EVENT_NOWA_OCENA, dane)
                self._wyslij_sms(TYP_OCENA, dane)

    def _fire_uwagi_events(self, uwagi: List[Dict]) -> None:
        """Wyslij zdarzenia HA (i SMS) dla nowych uwag."""
        for uwaga in uwagi:
            if uwaga["id"] in self._seen_uwagi_ids:
                continue
            self._seen_uwagi_ids.add(uwaga["id"])
            self._zmienione = True
            _LOGGER.debug("Nowa uwaga: %s %s", uwaga.get("data"), uwaga.get("tresc"))
            dane = {
                "tresc": uwaga.get("tresc", ""),
                "rodzaj": uwaga.get("rodzaj", ""),
                "kategoria": uwaga.get("kategoria", ""),
                "nauczyciel": uwaga.get("nauczyciel", ""),
                "data": uwaga.get("data", ""),
                "uczen": self._uczen,
            }
            self._ostatnia_nowa_uwaga = dane
            self.hass.bus.fire(EVENT_NOWA_UWAGA, dane)
            self._wyslij_sms(TYP_UWAGA, dane)

    def _fire_schedule_events(self, terminarz: List[Dict]) -> None:
        """Wyslij zdarzenia HA dla nowych zdarzen w kalendarzu."""
        for zdarzenie in terminarz:
            ev_id = self._id_zdarzenia(zdarzenie)
            if ev_id not in self._seen_schedule_ids:
                self._seen_schedule_ids.add(ev_id)
                self._zmienione = True
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
            hw_id = self._id_zadania(zadanie)
            if hw_id not in self._seen_homework_ids:
                self._seen_homework_ids.add(hw_id)
                self._zmienione = True
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


