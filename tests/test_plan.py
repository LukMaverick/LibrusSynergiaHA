"""Testy czystych funkcji planu lekcji."""

from datetime import date, datetime

from _builders import tydzien
from _pure import load

plan = load("plan")

PN = date(2026, 10, 12)


def test_poniedzialek_i_okno():
    assert PN.weekday() == 0
    assert plan.poniedzialek(date(2026, 10, 18)) == PN
    assert plan.poniedzialek(PN) == PN
    assert plan.przytnij_do_okna(date(2026, 10, 14), PN, 2, 4) == PN
    assert plan.przytnij_do_okna(date(2026, 12, 14), PN, 2, 4) is None  # +9 tygodni
    assert plan.przytnij_do_okna(date(2026, 9, 28), PN, 2, 4) == date(2026, 9, 28)
    assert plan.przytnij_do_okna(date(2026, 9, 14), PN, 2, 4) is None


def test_normalizacja_lekcji_nauczyciel_sala_i_grupy():
    t = tydzien(PN, {0: {
        1: ("Matematyka", "Jan Kowalski - s. 12", {}),
        2: ("Angielski / Niemiecki", "Anna Nowak - s. 3 / Hans Meier - s. 4", {}),
        3: ("Plastyka", "Ewa Lis", {}),
    }})
    dni = plan.normalizuj_tydzien(t)["dni"]
    mat, ang, pla = dni["2026-10-12"]
    assert (mat["nauczyciel"], mat["sala"]) == ("Jan Kowalski", "12")
    assert ang["grupy"] == ["Angielski", "Niemiecki"]
    assert ang["sala"] == "3"
    assert (pla["nauczyciel"], pla["sala"]) == ("Ewa Lis", "")


def test_puste_okienka_i_lekcja_zero():
    t = tydzien(PN, {0: {0: ("Religia", "", {}), 2: ("Matematyka", "", {})}})
    wynik = plan.normalizuj_tydzien(t)
    lekcje = wynik["dni"]["2026-10-12"]
    assert [l["numer"] for l in lekcje] == [0, 2]  # okienko to luka w numerach
    assert wynik["godziny"]["1"] == "08:00–08:45"  # godziny puste tez zapisane
    assert wynik["dni"]["2026-10-17"] == []  # sobota bez lekcji, ale dzien obecny


def test_zastepstwo_i_odwolanie():
    zast = {"Zastępstwo": {"teacher_swap": "Piotr Zet", "subject_swap": "", "classroom_swap": "", "date_added": "x"}}
    odw = {"Lekcja odwołana": ""}
    t = tydzien(PN, {0: {1: ("Matematyka", "", zast), 2: ("Polski", "", odw), 3: ("WF", "", {})}})
    l1, l2, l3 = plan.normalizuj_tydzien(t)["dni"]["2026-10-12"]
    assert l1["zastepstwo"] and not l1["odwolana"] and l1["zmiana"] == {"teacher_swap": "Piotr Zet"}
    assert l2["odwolana"] and not l2["zastepstwo"]
    assert not l3["zastepstwo"] and not l3["odwolana"] and l3["info"] == ""


def test_zakres_i_przedmioty_pomijaja_odwolane():
    t = tydzien(PN, {0: {
        1: ("Polski", "", {"Lekcja odwołana": ""}),
        2: ("Matematyka", "", {}),
        3: ("Matematyka", "", {}),
        4: ("Plastyka", "", {}),
    }})
    lekcje = plan.normalizuj_tydzien(t)["dni"]["2026-10-12"]
    d = plan.buduj_dzien("2026-10-12", lekcje)
    assert d["zakres"] == "08:55–11:30"
    assert d["przedmioty"] == ["Matematyka", "Plastyka"]
    assert d["liczba_lekcji"] == 3
    assert d["dzien"] == "poniedziałek" and d["skrot"] == "Pn"
    assert plan.zakres_dnia([]) == "Wolne"


def test_najblizszy_dzien_nauki_piatek_to_poniedzialek():
    p = {"2026-10-16": [{"x": 1}], "2026-10-17": [], "2026-10-18": [], "2026-10-19": [{"x": 1}]}
    assert plan.najblizszy_dzien_nauki(p, date(2026, 10, 16)) == date(2026, 10, 19)
    assert plan.najblizszy_dzien_nauki({}, date(2026, 10, 16)) is None


def _lekcje(do="14:00"):
    return [{"numer": 1, "od": "08:00", "do": do, "przedmiot": "X", "odwolana": False}]


def test_wybor_tygodnia():
    nast = date(2026, 10, 19)
    pelny = {
        "2026-10-16": _lekcje("14:30"),
        "2026-10-19": _lekcje(),
    }
    # sobota i niedziela -> nastepny
    assert plan.wybierz_tydzien(datetime(2026, 10, 17, 9, 0), pelny) == nast
    assert plan.wybierz_tydzien(datetime(2026, 10, 18, 20, 0), pelny) == nast
    # piatek przed i po ostatniej lekcji
    assert plan.wybierz_tydzien(datetime(2026, 10, 16, 9, 0), pelny) == PN
    assert plan.wybierz_tydzien(datetime(2026, 10, 16, 14, 30), pelny) == nast
    # srodek tygodnia
    assert plan.wybierz_tydzien(datetime(2026, 10, 14, 12, 0), {**pelny, "2026-10-14": _lekcje()}) == PN


def test_wybor_tygodnia_ferie_i_pusty_piatek():
    nast = date(2026, 10, 19)
    ferie = {"2026-10-12": [], "2026-10-19": _lekcje()}
    assert plan.wybierz_tydzien(datetime(2026, 10, 13, 10, 0), ferie) == nast
    # brak lekcji takze w nastepnym -> zostajemy na biezacym
    assert plan.wybierz_tydzien(datetime(2026, 10, 13, 10, 0), {"2026-10-12": []}) == PN
    # piatek bez lekcji (nic nie zostalo w tym tygodniu), a w nastepnym sa -> nastepny
    assert plan.wybierz_tydzien(datetime(2026, 10, 16, 9, 0), {"2026-10-16": [], "2026-10-19": _lekcje()}) == nast
    # piatek bez lekcji i bez planu nastepnego tygodnia: domyslny koniec zajec 15:00 nie przesuwa tygodnia
    tylko_biezacy = {"2026-10-16": [], "2026-10-14": _lekcje()}
    assert plan.wybierz_tydzien(datetime(2026, 10, 16, 14, 0), tylko_biezacy) == PN
    assert plan.wybierz_tydzien(datetime(2026, 10, 16, 15, 0), tylko_biezacy) == nast


def test_przelom_roku():
    # sobota 2026-12-26 -> poniedzialek 2026-12-28; piatek 2027-01-01 po lekcjach -> 2027-01-04
    assert plan.wybierz_tydzien(datetime(2026, 12, 26, 9, 0), {}) == date(2026, 12, 28)
    assert plan.wybierz_tydzien(datetime(2027, 1, 1, 16, 0), {}) == date(2027, 1, 4)
