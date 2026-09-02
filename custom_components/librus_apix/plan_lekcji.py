"""Czysta logika przetwarzania planu lekcji z Librusa.

Modul celowo nie importuje Home Assistanta ani biblioteki librus_apix,
dzieki czemu da sie go testowac samodzielnie.
"""

from datetime import date, datetime
from typing import Any, Dict, Iterable, List, Optional

# Nazwy dni tygodnia zwracane przez librus_apix.timetable.Period.weekday
# Wartosci trafiaja wprost na karty, wiec z polskimi znakami.
DNI_TYGODNIA_PL = {
    "Monday": "Poniedzia\u0142ek",
    "Tuesday": "Wtorek",
    "Wednesday": "\u015aroda",
    "Thursday": "Czwartek",
    "Friday": "Pi\u0105tek",
    "Saturday": "Sobota",
    "Sunday": "Niedziela",
}


# Mapowanie polskich znakow diakrytycznych na ASCII - etykiety z Librusa
# ("Zastepstwo", "Lekcja odwolana") pisane sa z ogonkami.
_OGONKI = str.maketrans(
    "\u0105\u0107\u0119\u0142\u0144\u00f3\u015b\u017a\u017c",
    "acelnoszz",
)


def _zawiera(tekst: str, *rdzenie: str) -> bool:
    """Sprawdz czy tekst zawiera ktorykolwiek z rdzeni, ignorujac wielkosc liter i ogonki."""
    maly = tekst.lower().translate(_OGONKI)
    return any(rdzen in maly for rdzen in rdzenie)


def _opis_zmiany(info: Dict[str, Any]) -> str:
    """Zwroc etykiete zmiany (np. 'Zastepstwo') z pola info okresu."""
    return "; ".join(k.strip() for k in info.keys() if k and k.strip()) if info else ""


def przetworz_plan(tygodnie: Iterable[Iterable[Iterable[Any]]]) -> List[Dict[str, Any]]:
    """Zamien surowy plan z librus_apix na plaska, posortowana liste lekcji.

    Args:
        tygodnie: kolekcja tygodni, gdzie kazdy tydzien to lista dni,
            a kazdy dzien to lista obiektow Period.

    Returns:
        Lista slownikow z polskimi kluczami, posortowana po dacie i numerze lekcji.
        Puste okienka (Period bez przedmiotu) sa pomijane.
    """
    lekcje: Dict[tuple, Dict[str, Any]] = {}

    for tydzien in tygodnie or []:
        for dzien in tydzien or []:
            for period in dzien or []:
                przedmiot = (getattr(period, "subject", "") or "").strip()
                if not przedmiot:
                    continue

                info = getattr(period, "info", None) or {}
                opis = _opis_zmiany(info)
                weekday = getattr(period, "weekday", "") or ""
                data = getattr(period, "date", "") or ""
                numer = getattr(period, "number", None)

                lekcje[(data, numer)] = {
                    "data": data,
                    "dzien_tygodnia": DNI_TYGODNIA_PL.get(weekday, weekday),
                    "numer": numer,
                    "przedmiot": przedmiot,
                    # Biblioteka sklada to pole dzielac tekst po "-", wiec w praktyce
                    # bywa to sama sala albo nauczyciel z sala - nie rozbijamy tego dalej.
                    "nauczyciel_sala": (
                        getattr(period, "teacher_and_classroom", "") or ""
                    ).strip(),
                    "od": (getattr(period, "date_from", "") or "").strip(),
                    "do": (getattr(period, "date_to", "") or "").strip(),
                    "przerwa_od": getattr(period, "next_recess_from", None),
                    "przerwa_do": getattr(period, "next_recess_to", None),
                    "odwolana": _zawiera(opis, "odwol"),
                    "zastepstwo": _zawiera(opis, "zastep"),
                    "info": opis,
                    "szczegoly": info,
                }

    return sorted(lekcje.values(), key=lambda l: (l["data"], l["numer"] or 0))


def _polacz(data: str, godzina: str) -> Optional[datetime]:
    """Zloz date (YYYY-MM-DD) i godzine (H:MM lub HH:MM) w datetime."""
    if not data or not godzina:
        return None
    try:
        return datetime.strptime(f"{data} {godzina}", "%Y-%m-%d %H:%M")
    except ValueError:
        return None


def lekcje_dnia(plan: List[Dict[str, Any]], dzien: date) -> List[Dict[str, Any]]:
    """Zwroc lekcje z podanego dnia."""
    iso = dzien.strftime("%Y-%m-%d")
    return [l for l in plan if l["data"] == iso]


def pogrupuj_wg_dni(plan: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    """Pogrupuj plan wedlug daty, zachowujac kolejnosc chronologiczna."""
    dni: Dict[str, List[Dict[str, Any]]] = {}
    for lekcja in plan:
        dni.setdefault(lekcja["data"], []).append(lekcja)
    return dni


def nastepna_lekcja(
    plan: List[Dict[str, Any]], teraz: datetime
) -> Optional[Dict[str, Any]]:
    """Znajdz trwajaca lub najblizsza przyszla lekcje.

    Lekcje odwolane sa pomijane. Zwraca kopie slownika lekcji wzbogacona
    o pola 'trwa_teraz' i 'za_minut' (0 dla lekcji trwajacej).
    """
    for lekcja in plan:
        if lekcja.get("odwolana"):
            continue

        start = _polacz(lekcja["data"], lekcja["od"])
        if start is None:
            continue
        koniec = _polacz(lekcja["data"], lekcja["do"])

        # Bez poprawnej godziny konca przyjmujemy, ze lekcja minela wraz ze startem.
        if (koniec or start) <= teraz:
            continue

        trwa = start <= teraz
        pozostalo = 0 if trwa else int((start - teraz).total_seconds() // 60)
        return {**lekcja, "trwa_teraz": trwa, "za_minut": pozostalo}

    return None


def _koniec_dnia(lekcje: List[Dict[str, Any]]) -> Optional[datetime]:
    """Zwroc moment zakonczenia ostatniej lekcji dnia (None gdy brak godzin)."""
    konce = [_polacz(l["data"], l["do"]) for l in lekcje]
    konce = [k for k in konce if k is not None]
    return max(konce) if konce else None


def dni_do_wyswietlenia(
    plan: List[Dict[str, Any]],
    teraz: datetime,
    maks_dni: Optional[int] = None,
) -> Dict[str, List[Dict[str, Any]]]:
    """Dni, ktorych ostatnia lekcja jeszcze sie nie skonczyla.

    Dzien bez czytelnych godzin zostaje zachowany - lepiej pokazac za duzo
    niz ukryc dane, ktorych nie umiemy zinterpretowac.

    Args:
        maks_dni: ogranicz wynik do tylu pierwszych dni. Dzieki temu karta
            pokazuje zawsze tyle samo dni, niezaleznie od tego, czy dzisiejsze
            lekcje juz sie skonczyly.
    """
    wynik: Dict[str, List[Dict[str, Any]]] = {}
    for data, lekcje in pogrupuj_wg_dni(plan).items():
        koniec = _koniec_dnia(lekcje)
        if koniec is None or koniec > teraz:
            wynik[data] = lekcje
            if maks_dni is not None and len(wynik) >= maks_dni:
                break
    return wynik


def biezacy_dzien(
    plan: List[Dict[str, Any]], teraz: datetime
) -> List[Dict[str, Any]]:
    """Lekcje dnia, ktory ma sens pokazac: dzisiejsze dopoki trwaja,
    a po ostatniej lekcji - najblizszy kolejny dzien z lekcjami."""
    for lekcje in dni_do_wyswietlenia(plan, teraz).values():
        return lekcje
    return []


def _numer_lekcji(wartosc: Any) -> Optional[int]:
    """Zamien numer lekcji z terminarza na int.

    Librus zwraca tu liczbe albo napis "unknown" dla wydarzen calodniowych.
    """
    if isinstance(wartosc, bool):
        return None
    if isinstance(wartosc, int):
        return wartosc
    if isinstance(wartosc, str) and wartosc.strip().isdigit():
        return int(wartosc.strip())
    return None


def _klucz_przedmiotu(nazwa: str) -> str:
    """Znormalizuj nazwe przedmiotu do porownan (terminarz bywa inaczej pisany)."""
    return (nazwa or "").strip().casefold()


def _data_iso(wartosc: str) -> Optional[str]:
    """Sprowadz date do formatu YYYY-MM-DD, tolerujac zapis z kropkami."""
    tekst = (wartosc or "").strip()
    for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%Y.%m.%d", "%d-%m-%Y"):
        try:
            return datetime.strptime(tekst, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


def _skrot_wydarzenia(zdarzenie: Dict[str, Any]) -> Dict[str, Any]:
    """Zostaw z wydarzenia tylko to, co przydaje sie na karcie."""
    szczegoly = zdarzenie.get("szczegoly") or {}
    return {
        "tytul": zdarzenie.get("tytul", ""),
        "przedmiot": zdarzenie.get("przedmiot", ""),
        "opis": szczegoly.get("Opis", "") if isinstance(szczegoly, dict) else "",
        "nauczyciel": szczegoly.get("Nauczyciel", "") if isinstance(szczegoly, dict) else "",
        "godzina": zdarzenie.get("godzina", ""),
    }


def _skrot_zadania(zadanie: Dict[str, Any]) -> Dict[str, Any]:
    """Zostaw z zadania domowego tylko to, co przydaje sie na karcie."""
    return {
        "przedmiot": zadanie.get("przedmiot", ""),
        "kategoria": zadanie.get("kategoria", ""),
        "termin": zadanie.get("termin", ""),
        "nauczyciel": zadanie.get("nauczyciel", ""),
    }


def polacz_z_wydarzeniami(
    plan: List[Dict[str, Any]],
    terminarz: Optional[List[Dict[str, Any]]] = None,
    zadania: Optional[List[Dict[str, Any]]] = None,
) -> tuple:
    """Przypnij wydarzenia z terminarza i prace domowe do lekcji.

    Dopasowanie wydarzenia: najpierw po numerze lekcji (gdy Librus go poda),
    potem po nazwie przedmiotu. Czego nie da sie przypiac do konkretnej lekcji
    (wywiadowka, dzien wolny), trafia do wydarzen calodniowych.

    Prace domowe przypinane sa do dnia, w ktorym mija ich termin.

    Returns:
        (plan z polami "wydarzenia" i "zadania", wydarzenia_dnia, zadania_dnia)
    """
    wzbogacony = [{**l, "wydarzenia": [], "zadania": []} for l in plan]
    wg_dnia: Dict[str, List[Dict[str, Any]]] = {}
    for lekcja in wzbogacony:
        wg_dnia.setdefault(lekcja["data"], []).append(lekcja)

    wydarzenia_dnia: Dict[str, List[Dict[str, Any]]] = {}
    zadania_dnia: Dict[str, List[Dict[str, Any]]] = {}

    def _dopasuj(dzien: str, przedmiot: str, numer: Optional[int]) -> List[Dict[str, Any]]:
        lekcje = wg_dnia.get(dzien, [])
        if numer is not None:
            trafienia = [l for l in lekcje if l["numer"] == numer]
            if trafienia:
                return trafienia
        klucz = _klucz_przedmiotu(przedmiot)
        return [l for l in lekcje if klucz and _klucz_przedmiotu(l["przedmiot"]) == klucz]

    for zdarzenie in terminarz or []:
        dzien = _data_iso(zdarzenie.get("data", ""))
        if dzien is None:
            continue
        skrot = _skrot_wydarzenia(zdarzenie)
        trafienia = _dopasuj(
            dzien, zdarzenie.get("przedmiot", ""), _numer_lekcji(zdarzenie.get("numer_lekcji"))
        )
        if trafienia:
            for lekcja in trafienia:
                lekcja["wydarzenia"].append(skrot)
        elif dzien in wg_dnia:
            wydarzenia_dnia.setdefault(dzien, []).append(skrot)

    for zadanie in zadania or []:
        dzien = _data_iso(zadanie.get("termin", ""))
        if dzien is None:
            continue
        skrot = _skrot_zadania(zadanie)
        trafienia = _dopasuj(dzien, zadanie.get("przedmiot", ""), None)
        if trafienia:
            for lekcja in trafienia:
                lekcja["zadania"].append(skrot)
        elif dzien in wg_dnia:
            zadania_dnia.setdefault(dzien, []).append(skrot)

    return wzbogacony, wydarzenia_dnia, zadania_dnia
