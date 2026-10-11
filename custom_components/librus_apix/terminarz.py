"""Klasyfikacja i wzbogacanie zdarzen terminarza (czyste funkcje, bez Home Assistant)."""

from __future__ import annotations

import re
import unicodedata
from datetime import date, datetime, timedelta
from typing import Any, Dict, Iterable, List, Optional, Tuple

from .const import (
    DNI_TYGODNIA_PL,
    IKONY_TYPOW,
    REGULY_TYPOW,
    TYP_DOMYSLNY,
    TYPY_CALODNIOWE,
    TYPY_SPRAWDZIAN,
)

_NIEZNANE = {"", "unknown", "unspecified"}


def normalizuj_tekst(s: Any) -> str:
    """Male litery, bez polskich znakow i interpunkcji, pojedyncze spacje."""
    tekst = str(s or "").casefold().replace("ł", "l")
    tekst = unicodedata.normalize("NFKD", tekst)
    tekst = "".join(c for c in tekst if not unicodedata.combining(c))
    tekst = re.sub(r"[^a-z0-9]+", " ", tekst)
    return tekst.strip()


def _slowo_klucz(tekst: str, klucz: str) -> bool:
    """Czy klucz wystepuje jako poczatek slowa w tekscie (oba po normalizacji)."""
    return re.search(r"\b" + re.escape(klucz), tekst) is not None


def klasyfikuj(tekst: str, reguly: Optional[List] = None) -> str:
    """Zwroc typ zdarzenia wg slow kluczowych; pierwsza pasujaca regula wygrywa."""
    norm = normalizuj_tekst(tekst)
    for typ, slowa in reguly or REGULY_TYPOW:
        if any(_slowo_klucz(norm, normalizuj_tekst(s)) for s in slowa):
            return typ
    return TYP_DOMYSLNY


def parse_numer(n: Any) -> Optional[int]:
    """Numer lekcji z terminarza: tylko liczba calkowita 0-12 (odsiewa 'unknown' i godziny)."""
    try:
        wartosc = int(str(n).strip())
    except (TypeError, ValueError):
        return None
    return wartosc if 0 <= wartosc <= 12 else None


def _czysty(v: Any) -> Optional[str]:
    tekst = re.sub(r"<[^>]+>", " ", str(v or ""))
    tekst = re.sub(r"\s+", " ", tekst).strip()
    return None if normalizuj_tekst(tekst) in _NIEZNANE else tekst


def parsuj_szczegoly(szczegoly: Any) -> Tuple[Optional[str], Optional[str]]:
    """Wyciagnij (nauczyciel, opis) ze slownika albo napisu 'Nauczyciel: X<br />Opis: Y'."""
    pary: Dict[str, Any] = {}
    if isinstance(szczegoly, dict):
        pary = szczegoly
    elif isinstance(szczegoly, str):
        for kawalek in re.split(r"<br\s*/?>", szczegoly):
            if ":" in kawalek:
                k, v = kawalek.split(":", 1)
                pary[k] = v
    nauczyciel = opis = None
    for k, v in pary.items():
        nk = normalizuj_tekst(k)
        if nk == "nauczyciel":
            nauczyciel = _czysty(v)
        elif nk == "opis":
            opis = _czysty(v)
    return nauczyciel, opis


def parse_data(s: Any) -> Optional[date]:
    try:
        return datetime.strptime(str(s)[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def wzbogac_zdarzenie(ev: Dict[str, Any], dzis: date) -> Dict[str, Any]:
    """Nowy slownik: wszystkie stare klucze bez zmian plus pola przydatne karcie i automatyzacjom."""
    nauczyciel, opis = parsuj_szczegoly(ev.get("szczegoly"))
    przedmiot = _czysty(ev.get("przedmiot")) or ""
    tytul = str(ev.get("tytul") or "")
    if normalizuj_tekst(przedmiot) == normalizuj_tekst(tytul):
        przedmiot = ""
    # Nauczyciel celowo nie bierze udzialu w klasyfikacji (nazwisko "Test" itp.)
    typ = klasyfikuj(f"{tytul} {ev.get('przedmiot', '')} {opis or ''}")
    d = parse_data(ev.get("data"))
    return {
        **ev,
        "typ": typ,
        "ikona": IKONY_TYPOW.get(typ, IKONY_TYPOW[TYP_DOMYSLNY]),
        "wazne": typ in TYPY_SPRAWDZIAN,
        "calodniowe": typ in TYPY_CALODNIOWE,
        "dzien_tygodnia": DNI_TYGODNIA_PL[d.weekday()] if d else None,
        "dzien_tygodnia_nr": d.weekday() if d else None,
        "dni_do": (d - dzis).days if d else None,
        "nauczyciel": nauczyciel,
        "opis": opis,
        "lekcja": parse_numer(ev.get("numer_lekcji")),
        "przedmiot_czysty": przedmiot,
        "id": ev.get("href") or f"{ev.get('data')}|{tytul}|{ev.get('przedmiot')}",
    }


def wzbogac_terminarz(lista: Iterable[Dict[str, Any]], dzis: date) -> List[Dict[str, Any]]:
    """Wzbogac, odfiltruj przeszle i posortuj (dzien, calodniowe najpierw, lekcja, godzina)."""
    wynik = [
        w
        for w in (wzbogac_zdarzenie(e, dzis) for e in lista or [])
        if w["dni_do"] is not None and w["dni_do"] >= 0
    ]
    wynik.sort(
        key=lambda e: (
            e["data"],
            0 if e["calodniowe"] else 1,
            e["lekcja"] if e["lekcja"] is not None else 99,
            str(e.get("godzina") or ""),
            str(e.get("tytul") or ""),
        )
    )
    return wynik


def sprawdziany_w_oknie(zdarzenia: Iterable[Dict[str, Any]], dni: int = 7) -> List[Dict[str, Any]]:
    """Sprawdziany i kartkowki w ciagu `dni` dni (wlacznie z dzis), skrocone do pol istotnych."""
    return [
        {
            "data": e["data"],
            "typ": e["typ"],
            "przedmiot": e["przedmiot_czysty"] or e["tytul"],
            "tytul": e["tytul"],
            "dni_do": e["dni_do"],
        }
        for e in zdarzenia
        if e["wazne"] and 0 <= e["dni_do"] < dni
    ]


def podsumowanie(zdarzenia: List[Dict[str, Any]], dni: int = 7) -> Dict[str, Any]:
    typy: Dict[str, int] = {}
    for e in zdarzenia:
        typy[e["typ"]] = typy.get(e["typ"], 0) + 1
    okno = sprawdziany_w_oknie(zdarzenia, dni)
    wszystkie = [e for e in zdarzenia if e["wazne"]]
    najblizszy = None
    if wszystkie:
        e = wszystkie[0]
        najblizszy = {
            "data": e["data"],
            "typ": e["typ"],
            "przedmiot": e["przedmiot_czysty"] or e["tytul"],
            "tytul": e["tytul"],
            "dni_do": e["dni_do"],
        }
    return {
        "typy_zdarzen": typy,
        "sprawdziany_7_dni": okno,
        "liczba_sprawdzianow_7_dni": len(okno),
        "najblizszy_sprawdzian": najblizszy,
    }
