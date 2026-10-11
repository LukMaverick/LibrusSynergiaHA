"""Testy scalania planu z terminarzem i zadaniami."""

import copy
import json
from datetime import date

from _builders import fixture, homework, tydzien
from _pure import load

plan = load("plan")
sc = load("scalanie")
zad = load("zadania")

PN = date(2026, 10, 12)
DZIS = PN


def _plan():
    t = tydzien(PN, {
        0: {  # poniedzialek 12.10
            1: ("Język polski", "", {}),
            2: ("Matematyka", "Jan Kowalski - s. 12", {}),
            3: ("Wychowanie fizyczne", "", {}),
        },
        1: {1: ("Matematyka", "", {}), 2: ("Historia", "", {})},  # wtorek 13.10
        2: {1: ("Biologia", "", {})},  # sroda 14.10
        4: {1: ("Biologia", "", {}), 5: ("Angielski / Niemiecki", "", {})},  # piatek 16.10
    })
    return plan.normalizuj_tydzien(t)["dni"]


def _terminarz():
    return fixture("terminarz_pulapki.json")


def test_klasyfikator():
    assert sc.klasyfikuj("Sprawdzian z ułamków") == "sprawdzian"
    assert sc.klasyfikuj("KARTKÓWKA") == "kartkowka"
    assert sc.klasyfikuj("Dzień wolny od zajęć dydaktycznych") == "dzien_wolny"
    assert sc.klasyfikuj("Rada pedagogiczna") == "rada"
    assert sc.klasyfikuj("Wycieczka do muzeum") == "wycieczka"
    assert sc.klasyfikuj("Lekcja odwołana") == "odwolane"
    assert sc.klasyfikuj("Konkurs plastyczny") == "inne"
    assert sc.klasyfikuj("Radar pogodowy") == "inne"  # 'rada' nie lapie 'radar'
    assert sc.klasyfikuj("sprawdzian", [("x", ["sprawdzian"])]) == "x"


def test_parse_numer_odsiewa_godziny_i_unknown():
    assert sc.parse_numer(2) == 2
    assert sc.parse_numer("0") == 0
    assert sc.parse_numer("unknown") is None
    assert sc.parse_numer(15) is None
    assert sc.parse_numer(None) is None


def test_dopasowanie_po_dacie_i_numerze():
    t = [{"data": "2026-10-12", "tytul": "Sprawdzian", "przedmiot": "Matematyka", "numer_lekcji": 2,
          "szczegoly": {}, "href": "x"}]
    dni = sc.scal(_plan(), t, [])
    pon = dni["2026-10-12"]
    mat = next(l for l in pon["lekcje"] if l["numer"] == 2)
    assert mat["sprawdzian"] is True
    assert mat["wydarzenia"][0]["typ"] == "sprawdzian"
    assert pon["liczba_sprawdzianow"] == 1


def test_numer_nie_pasuje_do_przedmiotu_to_fallback_po_przedmiocie():
    # wtorek: Matematyka jest na lekcji 1, a terminarz twierdzi, ze na 2 (tam jest Historia)
    dni = sc.scal(_plan(), _terminarz(), [])
    wt = dni["2026-10-13"]
    mat = next(l for l in wt["lekcje"] if l["przedmiot"] == "Matematyka")
    assert mat["sprawdzian"] is True
    assert not next(l for l in wt["lekcje"] if l["przedmiot"] == "Historia")["sprawdzian"]
    # sprawdzian na lekcji + kartkowka z polskiego na poziomie dnia (polskiego we wtorek nie ma)
    assert wt["liczba_sprawdzianow"] == 2


def test_numer_15_z_godziny_nie_przypisuje_do_lekcji_wg_numeru():
    # Kartowka z numerem "15" i przedmiotem 'Jezyk polski' - wtorek nie ma polskiego,
    # wiec ma wyladowac w wydarzeniach dnia, a nie przy przypadkowej lekcji
    dni = sc.scal(_plan(), _terminarz(), [])
    wt = dni["2026-10-13"]
    assert any(w["typ"] == "kartkowka" for w in wt["wydarzenia_dnia"])
    assert not any(l["sprawdzian"] and l["przedmiot"] == "Historia" for l in wt["lekcje"])


def test_fallback_po_przedmiocie_gdy_numer_zly():
    dni = sc.scal(_plan(), _terminarz(), [])
    pt = dni["2026-10-16"]
    # Biologia numer 5 w terminarzu, ale w planie Biologia jest na lekcji 1 - dopasowanie po przedmiocie
    bio = next(l for l in pt["lekcje"] if l["przedmiot"] == "Biologia")
    assert bio["sprawdzian"] is True


def test_zdarzenia_calodniowe_i_dzien_wolny():
    dni = sc.scal(_plan(), _terminarz(), [])
    assert [w["typ"] for w in dni["2026-10-14"]["wydarzenia_dnia"]] == ["wycieczka"]
    sr = dni["2026-10-15"]  # czwartek: brak lekcji w planie + dzien wolny w terminarzu
    assert sr["dzien_wolny"] is True
    assert dni["2026-10-16"]["wydarzenia_dnia"][0]["typ"] == "rada"
    assert dni["2026-10-16"]["dzien_wolny"] is False  # rada nie oznacza dnia wolnego
    assert dni["2026-10-17"]["dzien_wolny"] is False  # sobota to nie "dzien wolny" w sensie planu


def test_dzien_powszedni_bez_lekcji_to_dzien_wolny():
    dni = sc.scal(_plan(), [], [])
    assert dni["2026-10-15"]["dzien_wolny"] is True  # czwartek bez lekcji
    assert dni["2026-10-12"]["dzien_wolny"] is False


def test_odwolana_lekcja_z_terminarza_przelicza_podsumowanie():
    t = [{"data": "2026-10-12", "tytul": "Lekcja odwołana", "przedmiot": "Wychowanie fizyczne",
          "numer_lekcji": 3, "szczegoly": {}, "href": "x"}]
    dni = sc.scal(_plan(), t, [])
    d = dni["2026-10-12"]
    wf = next(l for l in d["lekcje"] if l["numer"] == 3)
    assert wf["odwolana"] is True
    assert d["liczba_lekcji"] == 2
    assert d["zakres"] == "08:00–09:40"
    assert "Wychowanie fizyczne" not in d["przedmioty"]


def test_zadania_przy_pierwszej_lekcji_przedmiotu_lub_na_poziomie_dnia():
    zadania = zad.normalizuj_zadania([homework(**h) for h in fixture("zadania.json")], DZIS, {"z1": "Ćw. 3"})
    dni = sc.scal(_plan(), [], zadania)
    sr = dni["2026-10-14"]  # termin dwoch zadan z matematyki; w srode jest tylko Biologia
    assert sr["liczba_zadan"] == 2
    assert [w["typ"] for w in sr["wydarzenia_dnia"]] == ["zadanie", "zadanie"]
    pt = dni["2026-10-16"]  # praca klasowa z angielskiego, lekcja 'Angielski / Niemiecki'
    ang = next(l for l in pt["lekcje"] if l["numer"] == 5)
    assert ang["zadania"][0]["kategoria"] == "Praca klasowa"
    assert ang["sprawdzian"] is True


def test_zadanie_trafia_do_pasujacej_lekcji_z_trescia():
    t = tydzien(PN, {2: {1: ("Matematyka", "", {}), 2: ("Matematyka", "", {})}})
    zadania = zad.normalizuj_zadania(
        [homework(**{**fixture("zadania.json")[0]})], DZIS, {"z1": "Ćw. 3"}
    )
    dni = sc.scal(plan.normalizuj_tydzien(t)["dni"], [], zadania)
    l1, l2 = dni["2026-10-14"]["lekcje"]
    assert l1["zadania"] == [{"id": "z1", "kategoria": "Zadanie domowe", "tresc": "Ćw. 3", "przedmiot": "Matematyka"}]
    assert l2["zadania"] == []


def test_scal_nie_modyfikuje_wejscia():
    p = _plan()
    kopia = copy.deepcopy(p)
    sc.scal(p, _terminarz(), [])
    assert p == kopia


def test_rozmiar_atrybutow_tygodnia_miesci_sie_w_limicie():
    t = tydzien(PN, {i: {n: (f"Przedmiot dlugi {n}", "Jan Kowalski-Nowak - s. 12", {"Zastępstwo": {"teacher_swap": "Piotr", "subject_swap": "", "classroom_swap": "", "date_added": ""}}) for n in range(0, 7)} for i in range(5)})
    dni = sc.scal(plan.normalizuj_tydzien(t)["dni"], _terminarz(), [])
    kompakt = []
    for d in dni.values():
        kompakt.append({**d, "lekcje": [{k: v for k, v in l.items() if k not in ("nauczyciel", "grupy")} for l in d["lekcje"]]})
    assert len(json.dumps(kompakt, ensure_ascii=False)) < 16000
