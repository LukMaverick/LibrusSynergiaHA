"""Testy czystych funkcji zadan domowych."""

from datetime import date

from _builders import fixture, homework
from _pure import load

zad = load("zadania")

DZIS = date(2026, 10, 12)


def test_parse_data_formaty():
    assert zad.parse_data("2026-10-14 23:59") == date(2026, 10, 14)
    assert zad.parse_data("16.10.2026") == date(2026, 10, 16)
    assert zad.parse_data("5.1.2027 08:00") == date(2027, 1, 5)
    assert zad.parse_data("16-10-2026") == date(2026, 10, 16)
    assert zad.parse_data("brak") is None
    assert zad.parse_data("31.02.2026") is None
    assert zad.parse_data(None) is None


def test_pilnosc():
    assert zad.pilnosc(date(2026, 10, 12), DZIS) == "dzis"
    assert zad.pilnosc(date(2026, 10, 13), DZIS) == "jutro"
    assert zad.pilnosc(date(2026, 10, 19), DZIS) == "tydzien"
    assert zad.pilnosc(date(2026, 10, 20), DZIS) == "pozniej"
    assert zad.pilnosc(date(2026, 10, 8), DZIS) == "po_terminie"
    assert zad.pilnosc(None, DZIS) == "brak_terminu"


def _zadania():
    return zad.normalizuj_zadania([homework(**h) for h in fixture("zadania.json")], DZIS)


def test_normalizacja_sortowanie_i_bez_daty_na_koncu():
    z = _zadania()
    assert [x["przedmiot"] for x in z] == ["Geografia", "Matematyka", "Matematyka", "Język angielski", "Historia"]
    assert z[-1]["termin"] is None and z[-1]["pilnosc"] == "brak_terminu" and z[-1]["termin_raw"] == "brak"
    assert z[0]["pilnosc"] == "po_terminie"
    assert z[1]["termin"] == "2026-10-14" and z[1]["dni_do"] == 2


def test_dwa_zadania_z_tego_samego_przedmiotu_maja_rozne_id():
    z = _zadania()
    mat = [x for x in z if x["przedmiot"] == "Matematyka"]
    assert {m["id"] for m in mat} == {"z1", "z2"}


def test_id_bez_href_jest_stabilne_i_unikalne_przy_duplikatach():
    hw = homework(subject="WF", category="Zadanie", teacher="", lesson="1", task_date="2026-10-01",
                  completion_date="2026-10-14", href="")
    a = zad.normalizuj_zadania([hw, hw], DZIS)
    assert a[0]["id"] != a[1]["id"]
    assert a[0]["id"] == zad.normalizuj_zadania([hw], DZIS)[0]["id"]


def test_tresc_ze_szczegolow():
    assert zad.tresc_ze_szczegolow({"Treść:": "  Zrób  ćw. 3 \n i 4 "}) == "Zrób ćw. 3 i 4"
    assert zad.tresc_ze_szczegolow({"Nauczyciel": "X"}) is None
    assert len(zad.tresc_ze_szczegolow({"Opis": "a" * 1000})) == 300


def test_do_pobrania_tresci_limit_horyzont_i_znane():
    z = _zadania()
    wybrane = zad.do_pobrania_tresci(z, {"z1": "juz mam"}, horyzont_dni=7, limit=5)
    # z1 znane, z5 po terminie, Historia bez daty, angielski bez href
    assert [x["id"] for x in wybrane] == ["z2"]
    assert zad.do_pobrania_tresci(z, {}, 7, 1)[0]["id"] == "z1"


def test_tresci_z_cache_trafiaja_do_zadan():
    z = zad.normalizuj_zadania([homework(**h) for h in fixture("zadania.json")], DZIS, {"z1": "Ćw. 3"})
    assert next(x for x in z if x["id"] == "z1")["tresc"] == "Ćw. 3"


def test_do_zrobienia_laczy_zadania_i_sprawdziany():
    z = _zadania()
    dzien = {
        "przedmioty": ["Matematyka"],
        "lekcje": [{"przedmiot": "Matematyka", "wydarzenia": [{"typ": "sprawdzian", "tytul": "S", "przedmiot": ""}]}],
        "wydarzenia_dnia": [{"typ": "kartkowka", "tytul": "K", "przedmiot": "Polski"}, {"typ": "wycieczka"}],
    }
    r = zad.do_zrobienia(dzien, z, "2026-10-14")
    assert len(r["zadania"]) == 2
    assert [s["przedmiot"] for s in r["sprawdziany"]] == ["Matematyka", "Polski"]
    assert r["przedmioty_do_spakowania"] == ["Matematyka"]
    assert zad.do_zrobienia(None, z, "2026-10-30")["zadania"] == []
