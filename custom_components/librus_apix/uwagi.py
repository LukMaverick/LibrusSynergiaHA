"""Pobieranie uwag (i pochwal) ucznia ze strony Librus Synergia.

Biblioteka librus-apix nie obsluguje uwag, wiec pobieramy strone /uwagi na tej samej
sesji (Client) i parsujemy tabele. Parser jest odporny na dwa uklady strony:

1. tabela z naglowkiem (Data | Nauczyciel | Rodzaj | Kategoria | Tresc ...)
2. "widok alternatywny": osobna tabelka na kazda uwage, wiersze <th>Nazwa</th><td>Wartosc</td>

Wynik: lista slownikow {"data", "nauczyciel", "rodzaj", "kategoria", "tresc", "id"}.
"""

from __future__ import annotations

import hashlib
import logging
import re
from typing import Any, Dict, List, Optional

from bs4 import BeautifulSoup, Tag

from librus_apix.client import Client
from librus_apix.helpers import no_access_check
from librus_apix.urls import BASE_URL

_LOGGER = logging.getLogger(__name__)

UWAGI_URL = f"{BASE_URL}/uwagi"

# Mapowanie naglowkow kolumn Librusa na nasze klucze (po znormalizowaniu)
_KOLUMNY = {
    "data": ("data", "dodano", "termin"),
    "nauczyciel": ("nauczyciel", "dodal", "dodala", "wystawil", "autor"),
    "rodzaj": ("rodzaj", "typ"),
    "kategoria": ("kategoria",),
    "tresc": ("tresc", "uwaga", "opis", "komentarz"),
}

_DATA_RE = re.compile(r"\d{4}-\d{2}-\d{2}|\d{2}\.\d{2}\.\d{4}")


def _norm(tekst: str) -> str:
    """Znormalizuj naglowek: male litery, bez polskich znakow i bialych znakow."""
    tekst = tekst.lower().strip()
    zamiana = str.maketrans("ąćęłńóśźż", "acelnoszz")
    return " ".join(tekst.translate(zamiana).split())


def _klucz_kolumny(naglowek: str) -> Optional[str]:
    n = _norm(naglowek)
    for klucz, warianty in _KOLUMNY.items():
        if any(n.startswith(w) or w in n for w in warianty):
            return klucz
    return None


def _tekst(komorka: Tag) -> str:
    return " ".join(komorka.get_text(" ", strip=True).split())


def _pusta_uwaga() -> Dict[str, str]:
    return {"data": "", "nauczyciel": "", "rodzaj": "", "kategoria": "", "tresc": ""}


def _z_naglowkiem(tabela: Tag) -> List[Dict[str, str]]:
    """Uklad 1: tabela z wierszem naglowkowym."""
    wiersze = tabela.find_all("tr")
    if not wiersze:
        return []

    naglowki: List[Optional[str]] = []
    start = 0
    for i, wiersz in enumerate(wiersze):
        komorki = wiersz.find_all(["th", "td"], recursive=False)
        if not komorki:
            continue
        klucze = [_klucz_kolumny(_tekst(k)) for k in komorki]
        if sum(1 for k in klucze if k) >= 2:
            naglowki = klucze
            start = i + 1
            break

    if not naglowki:
        return []

    wynik: List[Dict[str, str]] = []
    for wiersz in wiersze[start:]:
        komorki = wiersz.find_all("td", recursive=False)
        if len(komorki) < 2:
            continue
        uwaga = _pusta_uwaga()
        for klucz, komorka in zip(naglowki, komorki):
            if klucz:
                uwaga[klucz] = _tekst(komorka)
        if uwaga["tresc"] or uwaga["data"]:
            wynik.append(uwaga)
    return wynik


def _klucz_wartosc(tabela: Tag) -> List[Dict[str, str]]:
    """Uklad 2: wiersze <th>Nazwa</th><td>Wartosc</td> - jedna tabela = jedna uwaga."""
    uwaga = _pusta_uwaga()
    trafienia = 0
    for wiersz in tabela.find_all("tr"):
        th = wiersz.find("th")
        td = wiersz.find("td")
        if th is None or td is None:
            continue
        klucz = _klucz_kolumny(_tekst(th))
        if klucz:
            uwaga[klucz] = _tekst(td)
            trafienia += 1
    return [uwaga] if trafienia >= 2 and (uwaga["tresc"] or uwaga["data"]) else []


def _id_uwagi(uwaga: Dict[str, str]) -> str:
    surowe = "|".join(uwaga.get(k, "") for k in ("data", "nauczyciel", "rodzaj", "kategoria", "tresc"))
    return hashlib.md5(surowe.encode("utf-8")).hexdigest()[:12]


def parsuj_uwagi(html: str) -> List[Dict[str, str]]:
    """Sparsuj HTML strony /uwagi na liste uwag."""
    soup = no_access_check(BeautifulSoup(html, "lxml"))
    wynik: List[Dict[str, str]] = []

    tabele = soup.select("table.decorated") or soup.find_all("table")
    for tabela in tabele:
        # pomin tabele zagniezdzone (przetwarzamy najbardziej zewnetrzne)
        if tabela.find_parent("table") is not None:
            continue
        uwagi = _z_naglowkiem(tabela)
        if not uwagi:
            uwagi = _klucz_wartosc(tabela)
        wynik.extend(uwagi)

    if not wynik:
        # Pomoc w diagnostyce ukladu strony - uzytkownik moze wkleic ten log do issue
        for tabela in tabele[:5]:
            _LOGGER.debug("Uwagi: nierozpoznana tabela: %s", _tekst(tabela)[:400])

    for uwaga in wynik:
        if not _DATA_RE.search(uwaga["data"]):
            # sprobuj znalezc date w innych polach (np. gdy kolumny sa przesuniete)
            for wartosc in uwaga.values():
                m = _DATA_RE.search(wartosc)
                if m:
                    uwaga["data"] = m.group(0)
                    break
        uwaga["id"] = _id_uwagi(uwaga)

    return wynik


def pobierz_uwagi(client: Client) -> List[Dict[str, Any]]:
    """Pobierz i sparsuj uwagi (funkcja blokujaca - uruchamiac w executorze)."""
    response = client.get(UWAGI_URL)
    return parsuj_uwagi(response.text)
