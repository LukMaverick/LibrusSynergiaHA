"""Testy czystej logiki terminarza (terminarz.py) i sensorow terminarza."""

import json
import locale
from datetime import date
from pathlib import Path

import pytest

import _ha_stub
from _pure import load

terminarz = load("terminarz")
FIX = Path(__file__).parent / "fixtures"
DZIS = date(2026, 10, 12)  # poniedzialek


def _wczytaj(nazwa):
    return json.loads((FIX / nazwa).read_text(encoding="utf-8"))


@pytest.mark.parametrize("p", _wczytaj("terminarz_typy.json"))
def test_klasyfikacja_wg_fiksury(p):
    tekst = f"{p['tytul']} {p['przedmiot']} {p['opis']}"
    assert terminarz.klasyfikuj(tekst) == p["typ"], tekst


def test_nauczyciel_nie_wplywa_na_typ():
    ev = {
        "data": "2026-10-13",
        "tytul": "Lekcja",
        "przedmiot": "Chemia",
        "szczegoly": {"Nauczyciel": "Anna Test", "Opis": "Doswiadczenia"},
        "href": "x",
    }
    assert terminarz.wzbogac_zdarzenie(ev, DZIS)["typ"] == "inne"


def test_parsuj_szczegoly_dict_string_i_unknown():
    assert terminarz.parsuj_szczegoly({"Nauczyciel": "Jan Kowalski", "Opis": "Ułamki"}) == ("Jan Kowalski", "Ułamki")
    assert terminarz.parsuj_szczegoly("Nauczyciel: Jan<br />Opis: Dzialy<b>!</b>") == ("Jan", "Dzialy !")
    assert terminarz.parsuj_szczegoly({"Nauczyciel": "unknown", "Opis": ""}) == (None, None)
    assert terminarz.parsuj_szczegoly(None) == (None, None)
    assert terminarz.parsuj_szczegoly({}) == (None, None)


def test_parse_numer():
    assert terminarz.parse_numer(2) == 2
    assert terminarz.parse_numer("15") is None
    assert terminarz.parse_numer("unknown") is None
    assert terminarz.parse_numer(None) is None


def test_wzbogac_zachowuje_stare_klucze_i_dodaje_nowe():
    ev = {
        "data": "2026-10-14",
        "tydzien": "Wednesday",
        "tytul": "Sprawdzian",
        "przedmiot": "Matematyka",
        "godzina": "08:05",
        "numer_lekcji": 2,
        "szczegoly": {"Nauczyciel": "Jan", "Opis": "Ułamki"},
        "href": "h1",
    }
    w = terminarz.wzbogac_zdarzenie(ev, DZIS)
    assert {**ev}.items() <= w.items()
    assert w["typ"] == "sprawdzian" and w["wazne"] is True and w["calodniowe"] is False
    assert w["dni_do"] == 2
    assert w["dzien_tygodnia"] == "środa" and w["dzien_tygodnia_nr"] == 2
    assert w["lekcja"] == 2 and w["nauczyciel"] == "Jan" and w["opis"] == "Ułamki"
    assert w["przedmiot_czysty"] == "Matematyka" and w["id"] == "h1"


def test_przedmiot_czysty_pusty_dla_unspecified_i_rownego_tytulowi():
    base = {"data": "2026-10-13", "szczegoly": {}, "href": ""}
    a = terminarz.wzbogac_zdarzenie({**base, "tytul": "Wycieczka", "przedmiot": "unspecified"}, DZIS)
    b = terminarz.wzbogac_zdarzenie({**base, "tytul": "Wycieczka", "przedmiot": "wycieczka"}, DZIS)
    assert a["przedmiot_czysty"] == "" and b["przedmiot_czysty"] == ""
    assert a["id"] == "2026-10-13|Wycieczka|unspecified"


def test_dzien_tygodnia_niezalezny_od_locale():
    ev = {"data": "2026-10-14", "tytul": "x", "przedmiot": "y", "szczegoly": {}}
    for nazwa in ("C", "pl_PL.UTF-8"):
        try:
            locale.setlocale(locale.LC_TIME, nazwa)
        except locale.Error:
            continue
        assert terminarz.wzbogac_zdarzenie(ev, DZIS)["dzien_tygodnia"] == "środa"
    locale.setlocale(locale.LC_TIME, "C")


def test_wzbogac_terminarz_filtr_i_sortowanie():
    lista = _wczytaj("terminarz_pulapki.json") + [
        {"data": "2026-10-01", "tytul": "Stary sprawdzian", "przedmiot": "X", "szczegoly": {}, "href": "old"}
    ]
    wynik = terminarz.wzbogac_terminarz(lista, date(2026, 10, 13))
    assert all(e["dni_do"] >= 0 for e in wynik)
    assert "old" not in [e["id"] for e in wynik]
    dzien = [e for e in wynik if e["data"] == "2026-10-13"]
    # calodniowych brak; lekcja 2 przed lekcja nieznana (None na koncu)
    assert [e["id"] for e in dzien][0] == "t1"
    assert dzien[-1]["lekcja"] is None
    assert [e["data"] for e in wynik] == sorted(e["data"] for e in wynik)
    wolne = [e for e in wynik if e["data"] == "2026-10-16"]
    assert wolne[0]["calodniowe"] is True  # rada przed kartkowka w tym samym dniu


def test_podsumowanie_okno_7_dni_i_najblizszy():
    lista = _wczytaj("terminarz_pulapki.json")
    z = terminarz.wzbogac_terminarz(lista, date(2026, 10, 13))
    p = terminarz.podsumowanie(z)
    assert p["typy_zdarzen"]["sprawdzian"] == 1
    assert p["liczba_sprawdzianow_7_dni"] == 3  # sprawdzian, 2 kartkowki
    assert p["najblizszy_sprawdzian"]["dni_do"] == 0
    assert terminarz.podsumowanie([])["najblizszy_sprawdzian"] is None
    daleko = terminarz.wzbogac_terminarz(
        [{"data": "2026-12-01", "tytul": "Sprawdzian", "przedmiot": "M", "szczegoly": {}}], date(2026, 10, 13)
    )
    pd = terminarz.podsumowanie(daleko)
    assert pd["liczba_sprawdzianow_7_dni"] == 0
    assert pd["najblizszy_sprawdzian"]["dni_do"] == 49


@pytest.mark.skipif(not _ha_stub.STUBBED, reason="atrapy HA")
def test_sensor_terminarza_zgodnosc_wsteczna_i_nowe_atrybuty():
    from _pure import load_full

    sensor = load_full("sensor")
    dt = __import__("sys").modules["homeassistant.util.dt"]
    from datetime import datetime

    dt.now = lambda: datetime(2026, 10, 13, 12, 0).astimezone()
    coordinator = type("C", (), {"data": {"terminarz": _wczytaj("terminarz_pulapki.json")}})()
    s = sensor.LibrusTerminarzSensor(coordinator, type("E", (), {"entry_id": "e1"})())
    attrs = s.extra_state_attributes
    for klucz in ("zdarzenia", "liczba_zdarzen", "typy"):
        assert klucz in attrs
    assert attrs["typy"]["Kartkówka"] == 2
    assert attrs["liczba_zdarzen"] == len(attrs["zdarzenia"]) == s.native_value
    for klucz in ("typy_zdarzen", "liczba_sprawdzianow_7_dni", "najblizszy_sprawdzian", "zakres_do", "wersja_integracji"):
        assert klucz in attrs
    assert "zdarzenia" in sensor.LibrusTerminarzSensor._unrecorded_attributes

    spr = sensor.LibrusSprawdzianySensor(coordinator, type("E", (), {"entry_id": "e1"})())
    assert spr.native_value == 3
    assert spr.extra_state_attributes["najblizszy"]["dni_do"] == 0
