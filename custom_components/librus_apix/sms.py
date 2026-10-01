"""Wysylka powiadomien SMS przez wlasny serwer HTTP (bramke SMS).

Uzytkownik podaje w opcjach integracji jeden lub wiecej adresow (kazdy w osobnej
linii), np.:

    https://sms.example.pl/send?code=TAJNY&przedmiot=%przedmiot%&ocena=%ocena%&konto=Max

lub (bramka z jednym parametrem z trescia):

    https://www.example.pl/smsgateway/48XXXXXXXXX?text=%tekst%

Placeholdery %nazwa% (patrz const.SMS_PLACEHOLDERS) sa zamieniane na wartosci
zakodowane do URL. %tekst% to gotowa tresc SMS zbudowana z osobnego szablonu
tresci (zbuduj_tekst). Kazda linia = osobne zadanie HTTP GET.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Mapping
from urllib.parse import parse_qsl, quote, urlsplit, urlunsplit

import aiohttp
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    CONF_PUSH_NOTIFY,
    CONF_SMS_ENABLED,
    CONF_SMS_HEADERS,
    CONF_SMS_METHOD,
    CONF_SMS_TEKST_OCENY,
    CONF_SMS_TEKST_UWAGI,
    CONF_SMS_URL_OCENY,
    CONF_SMS_URL_UWAGI,
    CONF_SMS_VERIFY_SSL,
    DEFAULT_PUSH_TYTUL_OCENY,
    DEFAULT_PUSH_TYTUL_UWAGI,
    DEFAULT_SMS_ENABLED,
    DEFAULT_SMS_METHOD,
    DEFAULT_SMS_TEKST_OCENY,
    DEFAULT_SMS_TEKST_UWAGI,
    DEFAULT_SMS_VERIFY_SSL,
    METHOD_GET,
    METHOD_POST,
    METHOD_POST_JSON,
    SMS_PLACEHOLDERS,
    SMS_TIMEOUT,
    TYP_OCENA,
)

_LOGGER = logging.getLogger(__name__)


def podziel_adresy(tekst: str | None) -> List[str]:
    """Rozbij pole wieloliniowe na liste adresow (pomija puste linie i komentarze #)."""
    if not tekst:
        return []
    adresy: List[str] = []
    for linia in str(tekst).splitlines():
        linia = linia.strip()
        if not linia or linia.startswith("#"):
            continue
        adresy.append(linia)
    return adresy


def waliduj_adresy(tekst: str | None) -> List[str]:
    """Zwroc liste linii, ktore nie sa poprawnymi adresami http(s)."""
    bledne: List[str] = []
    for adres in podziel_adresy(tekst):
        czesci = urlsplit(adres)
        if czesci.scheme not in ("http", "https") or not czesci.netloc:
            bledne.append(adres)
    return bledne


def parsuj_naglowki(tekst: str | None) -> Dict[str, str]:
    """Pole wieloliniowe 'Nazwa: wartosc' -> slownik naglowkow HTTP (pomija puste i komentarze #)."""
    naglowki: Dict[str, str] = {}
    for linia in podziel_adresy(tekst):
        if ":" not in linia:
            continue
        nazwa, wartosc = linia.split(":", 1)
        nazwa = nazwa.strip()
        if nazwa:
            naglowki[nazwa] = wartosc.strip()
    return naglowki


def waliduj_naglowki(tekst: str | None) -> List[str]:
    """Zwroc linie, ktore nie maja formatu 'Nazwa: wartosc'."""
    return [l for l in podziel_adresy(tekst) if ":" not in l or not l.split(":", 1)[0].strip()]


def zbuduj_tekst(szablon: str | None, dane: Dict[str, Any]) -> str:
    """Podstaw placeholdery %nazwa% w szablonie tresci SMS (bez kodowania URL)."""
    tekst = szablon or ""
    for klucz in SMS_PLACEHOLDERS:
        if klucz == "tekst":
            continue
        znacznik = f"%{klucz}%"
        if znacznik in tekst:
            wartosc = dane.get(klucz)
            tekst = tekst.replace(znacznik, "" if wartosc is None else str(wartosc))
    return " ".join(tekst.split())


def zbuduj_url(szablon: str, dane: Dict[str, Any]) -> str:
    """Podstaw placeholdery %nazwa% w szablonie adresu (wartosci zakodowane do URL)."""
    url = szablon
    for klucz in SMS_PLACEHOLDERS:
        znacznik = f"%{klucz}%"
        if znacznik not in url:
            continue
        wartosc = dane.get(klucz)
        wartosc = "" if wartosc is None else str(wartosc)
        url = url.replace(znacznik, quote(wartosc, safe=""))
    return url


def _host(url: str) -> str:
    """Zwroc sam host adresu (do logow - bez kodow/parametrow)."""
    try:
        return urlsplit(url).netloc or url
    except Exception:  # pylint: disable=broad-except
        return url


def rozdziel_post(url: str):
    """Dla POST: zwroc (adres bez query, parametry z query jako dict)."""
    czesci = urlsplit(url)
    parametry = dict(parse_qsl(czesci.query, keep_blank_values=True))
    adres = urlunsplit((czesci.scheme, czesci.netloc, czesci.path, "", czesci.fragment))
    return adres, parametry


async def async_wyslij_sms(
    hass: HomeAssistant,
    szablon: str,
    dane: Dict[str, Any],
    verify_ssl: bool = True,
    metoda: str = METHOD_GET,
    naglowki: Dict[str, str] | None = None,
) -> bool:
    """Wyslij jedno zadanie HTTP na adres zbudowany z szablonu. Zwraca True gdy HTTP < 400.

    Dodatkowe naglowki (np. Authorization) sa dolaczane do kazdego zadania. Dane logowania
    w adresie (https://user:haslo@host/...) sa uzywane jako HTTP Basic Auth.

    GET       - parametry zostaja w adresie.
    POST      - parametry z czesci ?a=b&c=d adresu ida w body (form-urlencoded).
    POST JSON - jak wyzej, ale body to JSON {"a": "b", "c": "d"}.
    """
    url = zbuduj_url(szablon, dane)
    host = _host(url)
    _LOGGER.debug("Wysylam SMS (%s, %s) na %s: %s", dane.get("typ", "?"), metoda, host, url)

    session = async_get_clientsession(hass, verify_ssl=verify_ssl)
    timeout = aiohttp.ClientTimeout(total=SMS_TIMEOUT)
    naglowki = naglowki or {}
    try:
        if metoda == METHOD_POST:
            adres, parametry = rozdziel_post(url)
            zadanie = session.post(adres, data=parametry, headers=naglowki, timeout=timeout)
        elif metoda == METHOD_POST_JSON:
            adres, parametry = rozdziel_post(url)
            zadanie = session.post(adres, json=parametry, headers=naglowki, timeout=timeout)
        else:
            zadanie = session.get(url, headers=naglowki, timeout=timeout)

        async with zadanie as resp:
            tresc = (await resp.text())[:200]
            if resp.status >= 400:
                _LOGGER.error(
                    "Bramka SMS %s odpowiedziala HTTP %s: %s", host, resp.status, tresc
                )
                return False
            _LOGGER.info(
                "SMS wyslany przez %s (HTTP %s): %s", host, resp.status, tresc.strip()
            )
            return True
    except Exception as ex:  # pylint: disable=broad-except
        _LOGGER.error("Blad wysylki SMS przez %s: %s", host, ex)
        return False


async def async_wyslij_na_adresy(
    hass: HomeAssistant,
    adresy_tekst: str | None,
    dane: Dict[str, Any],
    verify_ssl: bool = True,
    metoda: str = METHOD_GET,
    naglowki: Dict[str, str] | None = None,
) -> int:
    """Wyslij SMS na kazdy adres z pola wieloliniowego. Zwraca liczbe udanych wysylek."""
    adresy = podziel_adresy(adresy_tekst)
    if not adresy:
        _LOGGER.debug("Brak adresow bramki SMS dla typu %s - pomijam", dane.get("typ"))
        return 0
    udane = 0
    for adres in adresy:
        if await async_wyslij_sms(hass, adres, dane, verify_ssl, metoda, naglowki):
            udane += 1
    return udane


def podziel_uslugi_notify(tekst: str | None) -> List[str]:
    """Pole wieloliniowe z uslugami notify -> lista nazw bez prefiksu 'notify.'."""
    uslugi = []
    for linia in podziel_adresy(tekst):
        nazwa = linia.strip()
        if nazwa.startswith("notify."):
            nazwa = nazwa[len("notify."):]
        if nazwa:
            uslugi.append(nazwa)
    return uslugi


async def async_wyslij_push(
    hass: HomeAssistant,
    uslugi_tekst: str | None,
    tytul: str,
    tekst: str,
) -> int:
    """Wyslij powiadomienie push przez uslugi notify.* HA (np. mobile_app_xxx). Zwraca liczbe udanych."""
    udane = 0
    for usluga in podziel_uslugi_notify(uslugi_tekst):
        if not hass.services.has_service("notify", usluga):
            _LOGGER.error("Usluga notify.%s nie istnieje - sprawdz nazwe w Narzedzia deweloperskie -> Akcje", usluga)
            continue
        try:
            await hass.services.async_call(
                "notify", usluga, {"title": tytul, "message": tekst}, blocking=True
            )
            _LOGGER.info("Push wyslany przez notify.%s", usluga)
            udane += 1
        except Exception as ex:  # pylint: disable=broad-except
            _LOGGER.error("Blad wysylki push przez notify.%s: %s", usluga, ex)
    return udane


def dane_testowe(typ: str, uczen: str = "") -> Dict[str, Any]:
    """Przykladowe dane do testowej wysylki (przycisk 'Test powiadomien' i opcje integracji)."""
    from datetime import date as _date

    dzis = _date.today().strftime("%Y-%m-%d")
    uczen = uczen or "Uczen"
    if typ == TYP_OCENA:
        return {
            "przedmiot": "Test (przedmiot)",
            "ocena": "5",
            "kategoria": "Test integracji",
            "nauczyciel": "Home Assistant",
            "data": dzis,
            "waga": 3,
            "komentarz": "To jest test z Home Assistant",
            "srednia": 4.5,
            "uczen": uczen,
        }
    return {
        "tresc": "To jest testowa uwaga z Home Assistant",
        "rodzaj": "pochwala",
        "kategoria": "Test integracji",
        "nauczyciel": "Home Assistant",
        "data": dzis,
        "uczen": uczen,
    }


# ------------------------------------------------------ wspolne: SMS + push

async def async_powiadom(
    hass: HomeAssistant,
    opcje: Mapping[str, Any],
    typ: str,
    dane: Dict[str, Any],
    *,
    sms: bool = True,
    push: bool = True,
    tekst: str | None = None,
) -> Dict[str, int]:
    """Wyslij powiadomienie o nowej ocenie/uwadze wszystkimi kanalami z opcji integracji.

    - SMS: gdy wlaczone (CONF_SMS_ENABLED) i sa adresy dla danego typu,
    - push: gdy podano uslugi notify.* (CONF_PUSH_NOTIFY).
    Zwraca {"sms": liczba_udanych, "push": liczba_udanych}.
    """
    dane = dict(dane)
    dane["typ"] = typ
    if typ == TYP_OCENA:
        adresy = opcje.get(CONF_SMS_URL_OCENY, "")
        szablon_tekstu = opcje.get(CONF_SMS_TEKST_OCENY, DEFAULT_SMS_TEKST_OCENY)
        tytul = DEFAULT_PUSH_TYTUL_OCENY
    else:
        adresy = opcje.get(CONF_SMS_URL_UWAGI, "")
        szablon_tekstu = opcje.get(CONF_SMS_TEKST_UWAGI, DEFAULT_SMS_TEKST_UWAGI)
        tytul = DEFAULT_PUSH_TYTUL_UWAGI
    dane["tekst"] = tekst or zbuduj_tekst(szablon_tekstu, dane)

    wynik = {"sms": 0, "push": 0}
    if sms and opcje.get(CONF_SMS_ENABLED, DEFAULT_SMS_ENABLED):
        wynik["sms"] = await async_wyslij_na_adresy(
            hass,
            adresy,
            dane,
            opcje.get(CONF_SMS_VERIFY_SSL, DEFAULT_SMS_VERIFY_SSL),
            opcje.get(CONF_SMS_METHOD, DEFAULT_SMS_METHOD),
            parsuj_naglowki(opcje.get(CONF_SMS_HEADERS, "")),
        )
    if push:
        wynik["push"] = await async_wyslij_push(
            hass, opcje.get(CONF_PUSH_NOTIFY, ""), zbuduj_tekst(tytul, dane), dane["tekst"]
        )
    return wynik
