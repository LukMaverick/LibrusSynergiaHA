"""Czyste funkcje planu lekcji (bez zaleznosci od Home Assistant)."""

from __future__ import annotations

import re
from datetime import date, datetime, time, timedelta
from typing import Any, Dict, Iterable, List, Optional

from .const import DNI_TYGODNIA_PL, KONIEC_ZAJEC_DOMYSLNIE, SKROTY_DNI_PL

_SALA_RE = re.compile(r"(?:\bs\.|\bsala)\s*([\w./-]+)", re.IGNORECASE)


def poniedzialek(d: date) -> date:
    """Zwroc poniedzialek tygodnia, w ktorym jest data d."""
    return d - timedelta(days=d.weekday())


def parse_iso(s: str) -> Optional[date]:
    """Parsuj date w formacie RRRR-MM-DD, zwroc None gdy sie nie da."""
    try:
        return datetime.strptime((s or "").strip()[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def nazwa_dnia(d: date) -> str:
    return DNI_TYGODNIA_PL[d.weekday()]


def skrot_dnia(d: date) -> str:
    return SKROTY_DNI_PL[d.weekday()]


def _rozbij_nauczyciela_i_sale(tekst: str) -> Dict[str, str]:
    """Rozbij tekst 'Imie Nazwisko - s. 12' na nauczyciela i sale (tolerancyjnie)."""
    tekst = (tekst or "").replace("\xa0", " ").strip()
    sala = ""
    m = _SALA_RE.search(tekst)
    if m:
        sala = m.group(1).strip(" .,;)")
        tekst = (tekst[: m.start()] + tekst[m.end():]).strip()
    nauczyciel = re.sub(r"\s+", " ", tekst).strip(" -,;()")
    return {"nauczyciel": nauczyciel, "sala": sala}


def _wartosc_info(info: Any) -> Dict[str, Any]:
    """Wyciagnij flagi zastepstwa/odwolania oraz tekst informacji z Period.info."""
    zastepstwo = False
    odwolana = False
    teksty: List[str] = []
    szczegoly: Dict[str, str] = {}
    if isinstance(info, dict):
        for klucz, wartosc in info.items():
            klucz_txt = str(klucz).strip()
            if klucz_txt:
                teksty.append(klucz_txt)
            niskie = klucz_txt.lower()
            if "odwo" in niskie:
                odwolana = True
            if "zast" in niskie:
                zastepstwo = True
            if isinstance(wartosc, dict):
                zastepstwo = zastepstwo or any(wartosc.get(k) for k in (
                    "teacher_swap", "subject_swap", "classroom_swap"))
                szczegoly = {k: v for k, v in wartosc.items() if v and k != "date_added"}
    elif isinstance(info, str) and info.strip():
        teksty.append(info.strip())
        if "odwo" in info.lower():
            odwolana = True
        if "zast" in info.lower():
            zastepstwo = True
    return {
        "zastepstwo": zastepstwo,
        "odwolana": odwolana,
        "info": "; ".join(teksty),
        "zmiana": szczegoly,
    }


def normalizuj_lekcje(p: Any) -> Dict[str, Any]:
    """Znormalizuj obiekt Period do slownika. Pusta lekcja ma pusty 'przedmiot'."""
    try:
        numer = int(str(getattr(p, "number", "")).strip())
    except (TypeError, ValueError):
        numer = None

    przedmiot = (getattr(p, "subject", "") or "").strip()
    tc = getattr(p, "teacher_and_classroom", "") or ""
    czesci = [c for c in (x.strip() for x in tc.split(" / ")) if c]
    rozbite = [_rozbij_nauczyciela_i_sale(c) for c in czesci]
    grupy = [s.strip() for s in przedmiot.split(" / ") if s.strip()] if przedmiot else []

    wynik = {
        "numer": numer,
        "od": getattr(p, "date_from", "") or "",
        "do": getattr(p, "date_to", "") or "",
        "przedmiot": przedmiot,
        "nauczyciel": rozbite[0]["nauczyciel"] if rozbite else "",
        "sala": rozbite[0]["sala"] if rozbite else "",
        "grupy": grupy if len(grupy) > 1 else [],
    }
    wynik.update(_wartosc_info(getattr(p, "info", None)))
    # Przy zastepstwie biblioteka podaje nowe dane w 'zmiana'
    return wynik


def normalizuj_tydzien(tydzien: Iterable[Iterable[Any]]) -> Dict[str, Any]:
    """Znormalizuj wynik get_timetable (7 list) do {'dni': {iso: [lekcje]}, 'godziny': {nr: 'od–do'}}.

    Do 'dni' trafiaja tylko niepuste lekcje; numeracja jest zachowana w polu 'numer',
    wiec okienka widac jako luki w numerach. Klucz dnia pochodzi z Period.date.
    """
    dni: Dict[str, List[Dict[str, Any]]] = {}
    godziny: Dict[str, str] = {}
    for dzien in tydzien:
        for p in dzien:
            iso = getattr(p, "date", "") or ""
            if parse_iso(iso) is None:
                continue
            dni.setdefault(iso, [])
            lekcja = normalizuj_lekcje(p)
            if lekcja["numer"] is not None and lekcja["od"] and lekcja["do"]:
                godziny.setdefault(str(lekcja["numer"]), f"{lekcja['od']}–{lekcja['do']}")
            if not lekcja["przedmiot"]:
                continue
            dni[iso].append(lekcja)
    for lekcje in dni.values():
        lekcje.sort(key=lambda l: (l["numer"] is None, l["numer"] if l["numer"] is not None else 0))
    return {"dni": dni, "godziny": godziny}


def zakres_dnia(lekcje: List[Dict[str, Any]]) -> str:
    """Zakres godzin 'HH:MM–HH:MM' od pierwszej do ostatniej nieodwolanej lekcji albo 'Wolne'."""
    aktywne = [l for l in lekcje if not l.get("odwolana") and l.get("od") and l.get("do")]
    if not aktywne:
        return "Wolne"
    return f"{aktywne[0]['od']}–{aktywne[-1]['do']}"


def przedmioty_dnia(lekcje: List[Dict[str, Any]]) -> List[str]:
    """Unikalne przedmioty (w kolejnosci lekcji), bez odwolanych."""
    wynik: List[str] = []
    for l in lekcje:
        if l.get("odwolana"):
            continue
        for nazwa in (l.get("grupy") or [l.get("przedmiot", "")]):
            if nazwa and nazwa not in wynik:
                wynik.append(nazwa)
    return wynik


def buduj_dzien(iso: str, lekcje: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Zbuduj slownik dnia na podstawie listy lekcji."""
    d = parse_iso(iso)
    aktywne = [l for l in lekcje if not l.get("odwolana")]
    return {
        "data": iso,
        "dzien": nazwa_dnia(d) if d else "",
        "skrot": skrot_dnia(d) if d else "",
        "liczba_lekcji": len(aktywne),
        "zakres": zakres_dnia(lekcje),
        "pierwsza": aktywne[0]["przedmiot"] if aktywne else "",
        "ostatnia": aktywne[-1]["przedmiot"] if aktywne else "",
        "przedmioty": przedmioty_dnia(lekcje),
        "lekcje": lekcje,
    }


def najblizszy_dzien_nauki(plan: Dict[str, List[Dict[str, Any]]], dzis: date) -> Optional[date]:
    """Pierwszy dzien po 'dzis' z lekcjami w planie (None gdy brak w zakresie planu)."""
    kandydaci = sorted(
        d for d in (parse_iso(k) for k, v in plan.items() if v) if d and d > dzis
    )
    return kandydaci[0] if kandydaci else None


def _ostatni_koniec(lekcje: List[Dict[str, Any]]) -> time:
    konce = []
    for l in lekcje:
        if l.get("odwolana"):
            continue
        try:
            konce.append(datetime.strptime(l.get("do", ""), "%H:%M").time())
        except ValueError:
            continue
    if konce:
        return max(konce)
    return datetime.strptime(KONIEC_ZAJEC_DOMYSLNIE, "%H:%M").time()


def wybierz_tydzien(now: datetime, plan: Dict[str, List[Dict[str, Any]]]) -> date:
    """Wybierz poniedzialek tygodnia pokazywanego domyslnie dla trybu automatycznego.

    Sobota/niedziela -> nastepny tydzien; piatek po ostatniej lekcji -> nastepny tydzien;
    brak lekcji do konca biezacego tygodnia (np. ferie), a w nastepnym sa -> nastepny.
    """
    dzis = now.date()
    biezacy = poniedzialek(dzis)
    nastepny = biezacy + timedelta(days=7)

    if dzis.weekday() >= 5:
        return nastepny

    lekcje_dzis = plan.get(dzis.isoformat(), [])
    if dzis.weekday() == 4 and now.time() >= _ostatni_koniec(lekcje_dzis):
        return nastepny

    zostaly = any(
        v
        for k, v in plan.items()
        if (d := parse_iso(k)) and d >= dzis and poniedzialek(d) == biezacy
    )
    w_nastepnym = any(
        v for k, v in plan.items() if (d := parse_iso(k)) and poniedzialek(d) == nastepny
    )
    if not zostaly and w_nastepnym:
        return nastepny
    return biezacy


def okno_tygodni(dzis: date, wstecz: int, naprzod: int) -> tuple:
    """Zwroc (najwczesniejszy, najpozniejszy) poniedzialek dozwolony w oknie."""
    b = poniedzialek(dzis)
    return b - timedelta(weeks=wstecz), b + timedelta(weeks=naprzod)


def przytnij_do_okna(d: date, dzis: date, wstecz: int, naprzod: int) -> Optional[date]:
    """Przytnij date do poniedzialku; zwroc None gdy poza oknem."""
    p = poniedzialek(d)
    od, do = okno_tygodni(dzis, wstecz, naprzod)
    return p if od <= p <= do else None
