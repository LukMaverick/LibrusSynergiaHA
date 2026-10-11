"""Scalanie planu lekcji z terminarzem i zadaniami (czyste funkcje, bez Home Assistant)."""

from __future__ import annotations

import copy
import re
import unicodedata
from datetime import date, timedelta
from typing import Any, Dict, Iterable, List, Optional

from .const import (
    IKONY_TYPOW,
    REGULY_TYPOW,
    TYP_DOMYSLNY,
    TYPY_CALODNIOWE,
    TYPY_SPRAWDZIAN,
)
from .plan import buduj_dzien, parse_iso

_NIEZNANY_PRZEDMIOT = {"", "unknown", "unspecified"}


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


def _przedmioty_zgodne(a: str, b: str) -> bool:
    na, nb = normalizuj_tekst(a), normalizuj_tekst(b)
    if not na or not nb:
        return False
    return na == nb or na in nb or nb in na


def _lekcja_pasuje(lekcja: Dict[str, Any], przedmiot: str) -> bool:
    nazwy = lekcja.get("grupy") or [lekcja.get("przedmiot", "")]
    return any(_przedmioty_zgodne(n, przedmiot) for n in nazwy)


def _tekst_zdarzenia(ev: Dict[str, Any]) -> str:
    szczegoly = ev.get("szczegoly")
    wartosci = " ".join(str(v) for v in szczegoly.values()) if isinstance(szczegoly, dict) else ""
    return f"{ev.get('tytul', '')} {ev.get('przedmiot', '')} {wartosci}"


def _wydarzenie(ev: Dict[str, Any], reguly: Optional[List]) -> Dict[str, Any]:
    typ = klasyfikuj(_tekst_zdarzenia(ev), reguly)
    przedmiot = str(ev.get("przedmiot") or "")
    if normalizuj_tekst(przedmiot) in _NIEZNANY_PRZEDMIOT:
        przedmiot = ""
    return {
        "typ": typ,
        "ikona": IKONY_TYPOW.get(typ, IKONY_TYPOW[TYP_DOMYSLNY]),
        "tytul": str(ev.get("tytul") or ""),
        "przedmiot": przedmiot,
        "href": str(ev.get("href") or ""),
    }


def _pierwsza_pasujaca(lekcje: List[Dict[str, Any]], przedmiot: str) -> Optional[Dict[str, Any]]:
    if not przedmiot:
        return None
    for l in lekcje:
        if not l.get("odwolana") and _lekcja_pasuje(l, przedmiot):
            return l
    return None


def _przypisz_zdarzenie(dzien: Dict[str, Any], ev: Dict[str, Any], surowe: Dict[str, Any]) -> None:
    lekcje = dzien["lekcje"]
    if ev["typ"] in TYPY_CALODNIOWE:
        dzien["wydarzenia_dnia"].append(ev)
        return

    # 1. data + numer lekcji; numer akceptujemy tylko przy znanym, zgodnym przedmiocie,
    # bo Event.number potrafi byc wyciagniety z godziny (np. "08:05" -> 5)
    numer = parse_numer(surowe.get("numer_lekcji"))
    lekcja = None
    if numer is not None and ev["przedmiot"]:
        lekcja = next(
            (l for l in lekcje if l.get("numer") == numer and _lekcja_pasuje(l, ev["przedmiot"])),
            None,
        )
    # 2. data + przedmiot
    if lekcja is None:
        lekcja = _pierwsza_pasujaca(lekcje, ev["przedmiot"])
    # 3. poziom dnia
    if lekcja is None:
        dzien["wydarzenia_dnia"].append(ev)
        return

    lekcja["wydarzenia"].append(ev)
    if ev["typ"] in TYPY_SPRAWDZIAN:
        lekcja["sprawdzian"] = True
    if ev["typ"] == "odwolane":
        lekcja["odwolana"] = True


def scal(
    plan_dni: Dict[str, List[Dict[str, Any]]],
    terminarz: Optional[Iterable[Dict[str, Any]]],
    zadania: Optional[Iterable[Dict[str, Any]]],
    reguly: Optional[List] = None,
) -> Dict[str, Dict[str, Any]]:
    """Scal plan (dict iso -> lekcje), terminarz i zadania w slowniki dni.

    Nie modyfikuje wejscia. Zdarzenia dopasowujemy do lekcji (data+numer, data+przedmiot),
    reszta trafia do 'wydarzenia_dnia'. Zadania ladują przy pierwszej lekcji przedmiotu
    w dniu terminu.
    """
    dni: Dict[str, Dict[str, Any]] = {}
    for iso, lekcje in plan_dni.items():
        kopia = copy.deepcopy(lekcje)
        for l in kopia:
            l.setdefault("wydarzenia", [])
            l.setdefault("sprawdzian", False)
            l.setdefault("zadania", [])
        dzien = buduj_dzien(iso, kopia)
        dzien["wydarzenia_dnia"] = []
        dni[iso] = dzien

    for surowe in terminarz or []:
        dzien = dni.get(surowe.get("data", ""))
        if dzien is None:
            continue
        _przypisz_zdarzenie(dzien, _wydarzenie(surowe, reguly), surowe)

    for z in zadania or []:
        dzien = dni.get(z.get("termin") or "")
        if dzien is None:
            continue
        wpis = {"id": z["id"], "kategoria": z["kategoria"], "tresc": z.get("tresc"), "przedmiot": z["przedmiot"]}
        lekcja = _pierwsza_pasujaca(dzien["lekcje"], z["przedmiot"])
        if lekcja is not None:
            lekcja["zadania"].append(wpis)
        else:
            dzien["wydarzenia_dnia"].append({
                "typ": "zadanie",
                "ikona": IKONY_TYPOW["zadanie"],
                "tytul": z["kategoria"] or "Zadanie",
                "przedmiot": z["przedmiot"],
                "href": z.get("href", ""),
            })
        if klasyfikuj(z["kategoria"], reguly) in TYPY_SPRAWDZIAN and lekcja is not None:
            lekcja["sprawdzian"] = True

    for iso, dzien in dni.items():
        data = parse_iso(iso)
        # Zdarzenia mogly oznaczyc lekcje jako odwolane - przelicz podsumowanie dnia
        dzien.update({k: v for k, v in buduj_dzien(iso, dzien["lekcje"]).items() if k != "lekcje"})
        wydarzenia = [w for l in dzien["lekcje"] for w in l["wydarzenia"]] + dzien["wydarzenia_dnia"]
        dzien["liczba_sprawdzianow"] = sum(
            1 for l in dzien["lekcje"] if l["sprawdzian"]
        ) + sum(1 for w in dzien["wydarzenia_dnia"] if w["typ"] in TYPY_SPRAWDZIAN)
        dzien["liczba_zadan"] = sum(len(l["zadania"]) for l in dzien["lekcje"]) + sum(
            1 for w in dzien["wydarzenia_dnia"] if w["typ"] == "zadanie"
        )
        dzien["dzien_wolny"] = any(w["typ"] == "dzien_wolny" for w in wydarzenia) or (
            data is not None and data.weekday() < 5 and not dzien["lekcje"]
        )
    return dni


def pusty_dzien(iso: str) -> Dict[str, Any]:
    """Dzien bez danych (np. brak pobranego tygodnia albo weekend)."""
    dzien = buduj_dzien(iso, [])
    dzien.update({
        "wydarzenia_dnia": [],
        "liczba_sprawdzianow": 0,
        "liczba_zadan": 0,
        "dzien_wolny": False,
    })
    return dzien


def kompaktuj_dzien(dzien: Dict[str, Any], max_info: int = 80, max_tresc: int = 120) -> Dict[str, Any]:
    """Zmniejsz dzien do atrybutow tygodnia: bez nauczyciela i grup, skrocone teksty."""
    lekcje = []
    for l in dzien.get("lekcje", []):
        k = {key: val for key, val in l.items() if key not in ("nauczyciel", "grupy")}
        k["info"] = (k.get("info") or "")[:max_info]
        k["zadania"] = [
            {**z, "tresc": (z.get("tresc") or "")[:max_tresc] or None} for z in k.get("zadania", [])
        ]
        lekcje.append(k)
    return {**dzien, "lekcje": lekcje}


def zbuduj_tydzien(
    dni: Dict[str, Dict[str, Any]],
    godziny: Dict[str, str],
    poniedzialek_tygodnia: date,
) -> Dict[str, Any]:
    """Zbuduj kompaktowy opis tygodnia (7 dni) z dni scalonych."""
    iso_dni = [(poniedzialek_tygodnia + timedelta(days=i)).isoformat() for i in range(7)]
    wynik_dni = [kompaktuj_dzien(dni.get(iso) or pusty_dzien(iso)) for iso in iso_dni]
    numery = [l["numer"] for d in wynik_dni for l in d["lekcje"] if l.get("numer") is not None]
    numery_lekcji = list(range(min(numery), max(numery) + 1)) if numery else []
    return {
        "tydzien_od": iso_dni[0],
        "tydzien_do": iso_dni[-1],
        "numery_lekcji": numery_lekcji,
        "godziny": {str(n): godziny[str(n)] for n in numery_lekcji if str(n) in godziny},
        "dni": wynik_dni,
    }
