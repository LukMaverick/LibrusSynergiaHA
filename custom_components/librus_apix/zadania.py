"""Czyste funkcje zadan domowych (bez zaleznosci od Home Assistant)."""

from __future__ import annotations

import hashlib
import re
from datetime import date
from typing import Any, Dict, Iterable, List, Optional

from .const import ZADANIA_TRESC_MAX_ZNAKOW

_FORMATY_DAT = (
    (re.compile(r"(\d{4})-(\d{2})-(\d{2})"), ("y", "m", "d")),
    (re.compile(r"(\d{1,2})\.(\d{1,2})\.(\d{4})"), ("d", "m", "y")),
    (re.compile(r"(\d{1,2})-(\d{1,2})-(\d{4})"), ("d", "m", "y")),
)
_ETYKIETY_TRESCI = ("tresc", "treść", "opis", "temat", "zadanie")


def parse_data(s: Any) -> Optional[date]:
    """Znajdz pierwsza poprawna date w tekscie (RRRR-MM-DD, DD.MM.RRRR, DD-MM-RRRR)."""
    tekst = str(s or "")
    for wzor, kolejnosc in _FORMATY_DAT:
        for m in wzor.finditer(tekst):
            czesci = dict(zip(kolejnosc, (int(x) for x in m.groups())))
            try:
                return date(czesci["y"], czesci["m"], czesci["d"])
            except ValueError:
                continue
    return None


def pilnosc(termin: Optional[date], dzis: date) -> str:
    """Okresl pilnosc zadania: dzis / jutro / tydzien / pozniej / po_terminie / brak_terminu."""
    if termin is None:
        return "brak_terminu"
    dni = (termin - dzis).days
    if dni < 0:
        return "po_terminie"
    if dni == 0:
        return "dzis"
    if dni == 1:
        return "jutro"
    if dni <= 7:
        return "tydzien"
    return "pozniej"


def id_zadania(hw: Any) -> str:
    """Stabilne id zadania: href z Librusa, a gdy pusty - skrot z pol zadania."""
    href = (getattr(hw, "href", "") or "").strip()
    if href:
        return href
    surowe = "|".join(
        str(getattr(hw, k, "") or "")
        for k in ("subject", "completion_date", "category", "lesson", "task_date")
    )
    return "h" + hashlib.sha1(surowe.encode("utf-8")).hexdigest()[:12]


def tresc_ze_szczegolow(szczegoly: Optional[Dict[str, str]]) -> Optional[str]:
    """Wybierz tresc zadania ze slownika szczegolow (pierwsza pasujaca etykieta)."""
    if not szczegoly:
        return None
    for etykieta, wartosc in szczegoly.items():
        e = str(etykieta).strip().lower().rstrip(":")
        if e in _ETYKIETY_TRESCI and str(wartosc).strip():
            tekst = re.sub(r"\s+", " ", str(wartosc)).strip()
            return tekst[:ZADANIA_TRESC_MAX_ZNAKOW]
    return None


def normalizuj_zadanie(hw: Any, dzis: date, tresc: Optional[str] = None) -> Dict[str, Any]:
    """Znormalizuj obiekt Homework do slownika."""
    termin_raw = getattr(hw, "completion_date", "") or ""
    zadano_raw = getattr(hw, "task_date", "") or ""
    termin = parse_data(termin_raw)
    zadano = parse_data(zadano_raw)
    return {
        "id": id_zadania(hw),
        "przedmiot": getattr(hw, "subject", "") or "",
        "kategoria": getattr(hw, "category", "") or "",
        "nauczyciel": getattr(hw, "teacher", "") or "",
        "lekcja": getattr(hw, "lesson", "") or "",
        "zadano": zadano.isoformat() if zadano else None,
        "zadano_raw": zadano_raw,
        "termin": termin.isoformat() if termin else None,
        "termin_raw": termin_raw,
        "dni_do": (termin - dzis).days if termin else None,
        "pilnosc": pilnosc(termin, dzis),
        "tresc": tresc,
        "href": getattr(hw, "href", "") or "",
    }


def normalizuj_zadania(
    homework_raw: Optional[Iterable[Any]],
    dzis: date,
    tresci: Optional[Dict[str, str]] = None,
) -> List[Dict[str, Any]]:
    """Znormalizuj liste Homework; sortuj po terminie, a zadania bez daty na koniec."""
    tresci = tresci or {}
    wynik = []
    uzyte: Dict[str, int] = {}
    for hw in homework_raw or []:
        z = normalizuj_zadanie(hw, dzis)
        # Dwa zadania o tym samym id (np. brak href) nie moga sie zlac
        n = uzyte.get(z["id"], 0)
        uzyte[z["id"]] = n + 1
        if n:
            z["id"] = f"{z['id']}_{n}"
        z["tresc"] = tresci.get(z["id"])
        wynik.append(z)
    wynik.sort(key=lambda z: (z["termin"] is None, z["termin"] or "", z["przedmiot"]))
    return wynik


def do_pobrania_tresci(
    zadania: List[Dict[str, Any]],
    znane: Dict[str, str],
    horyzont_dni: int,
    limit: int,
) -> List[Dict[str, Any]]:
    """Wybierz zadania, dla ktorych trzeba doczytac tresc: nowe id, termin w horyzoncie."""
    kandydaci = [
        z
        for z in zadania
        if z["id"] not in znane
        and z["href"]
        and z["dni_do"] is not None
        and 0 <= z["dni_do"] <= horyzont_dni
    ]
    return kandydaci[:limit]


def zadania_na_dzien(zadania: List[Dict[str, Any]], iso: str) -> List[Dict[str, Any]]:
    return [z for z in zadania if z["termin"] == iso]


def do_zrobienia(dzien: Optional[Dict[str, Any]], zadania: List[Dict[str, Any]], iso: str) -> Dict[str, Any]:
    """Zbierz rzeczy 'do zrobienia' na dany dzien: zadania, sprawdziany, przedmioty do spakowania."""
    sprawdziany: List[Dict[str, Any]] = []
    przedmioty: List[str] = []
    if dzien:
        przedmioty = list(dzien.get("przedmioty", []))
        for l in dzien.get("lekcje", []):
            for w in l.get("wydarzenia", []):
                if w.get("typ") in ("sprawdzian", "kartkowka"):
                    sprawdziany.append({**w, "przedmiot": w.get("przedmiot") or l.get("przedmiot", "")})
        for w in dzien.get("wydarzenia_dnia", []):
            if w.get("typ") in ("sprawdzian", "kartkowka"):
                sprawdziany.append(w)
    return {
        "data": iso,
        "zadania": zadania_na_dzien(zadania, iso),
        "sprawdziany": sprawdziany,
        "przedmioty_do_spakowania": przedmioty,
    }


def odswiez_pilnosc(zadania: List[Dict[str, Any]], dzis: date) -> List[Dict[str, Any]]:
    """Przelicz dni_do i pilnosc wzgledem dzis (np. po polnocy, bez nowego pobrania)."""
    wynik = []
    for z in zadania:
        termin = parse_data(z.get("termin"))
        wynik.append({
            **z,
            "dni_do": (termin - dzis).days if termin else None,
            "pilnosc": pilnosc(termin, dzis),
        })
    return wynik


def podsumuj_otwarte(zadania: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Zadania otwarte (nie po terminie) wraz z licznikami pilnosci i lista zadan po terminie."""
    otwarte = [z for z in zadania if z["pilnosc"] != "po_terminie"]
    return {
        "zadania": otwarte,
        "liczba_dzis": sum(1 for z in otwarte if z["pilnosc"] == "dzis"),
        "liczba_jutro": sum(1 for z in otwarte if z["pilnosc"] == "jutro"),
        "liczba_tydzien": sum(1 for z in otwarte if z["pilnosc"] in ("dzis", "jutro", "tydzien")),
        "po_terminie": [z for z in zadania if z["pilnosc"] == "po_terminie"],
    }


def zadanie_legacy(z: Dict[str, Any]) -> Dict[str, Any]:
    """Postac zadania zgodna wstecznie z sensorem 'Zadania' (surowe daty z Librusa + termin_iso)."""
    return {
        "przedmiot": z["przedmiot"],
        "kategoria": z["kategoria"],
        "nauczyciel": z["nauczyciel"],
        "lekcja": z["lekcja"],
        "data_zadania": z.get("zadano_raw", ""),
        "termin": z["termin_raw"],
        "termin_iso": z["termin"],
        "href": z["href"],
    }
