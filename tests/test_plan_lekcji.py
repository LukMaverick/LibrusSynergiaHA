"""Testy czystej logiki planu lekcji."""

from datetime import date, datetime
from types import SimpleNamespace

from custom_components.librus_apix.plan_lekcji import (
    biezacy_dzien,
    dni_do_wyswietlenia,
    lekcje_dnia,
    nastepna_lekcja,
    polacz_z_wydarzeniami,
    pogrupuj_wg_dni,
    przetworz_plan,
)


def period(
    subject="Matematyka",
    date_="2026-09-07",
    number=1,
    date_from="08:00",
    date_to="08:45",
    weekday="Monday",
    info=None,
    teacher_and_classroom=" 12",
    next_recess_from=None,
    next_recess_to=None,
):
    """Zbuduj atrape obiektu Period z librus_apix."""
    return SimpleNamespace(
        subject=subject,
        teacher_and_classroom=teacher_and_classroom,
        date=date_,
        date_from=date_from,
        date_to=date_to,
        weekday=weekday,
        info=info or {},
        number=number,
        next_recess_from=next_recess_from,
        next_recess_to=next_recess_to,
    )


def tydzien(*periods):
    """Owin okresy w strukture tygodnia (lista dni, kazdy dzien to lista okresow)."""
    return [list(periods)]


def test_przetworz_plan_pomija_puste_okienka():
    plan = przetworz_plan([tydzien(period(subject=""), period(subject="  "), period())])

    assert len(plan) == 1
    assert plan[0]["przedmiot"] == "Matematyka"


def test_przetworz_plan_tlumaczy_dzien_i_sortuje():
    plan = przetworz_plan(
        [
            tydzien(
                period(date_="2026-09-08", number=2, weekday="Tuesday"),
                period(date_="2026-09-07", number=3, weekday="Monday"),
                period(date_="2026-09-07", number=1, weekday="Monday"),
            )
        ]
    )

    assert [(l["data"], l["numer"]) for l in plan] == [
        ("2026-09-07", 1),
        ("2026-09-07", 3),
        ("2026-09-08", 2),
    ]
    assert plan[0]["dzien_tygodnia"] == "Poniedziałek"
    assert plan[-1]["dzien_tygodnia"] == "Wtorek"


def test_przetworz_plan_wykrywa_zastepstwo_i_odwolanie():
    plan = przetworz_plan(
        [
            tydzien(
                period(number=1, info={"Zastępstwo": {"teacher_swap": "Nowak"}}),
                period(number=2, info={"Lekcja odwołana": ""}),
                period(number=3),
            )
        ]
    )

    zastepstwo, odwolana, zwykla = plan
    assert zastepstwo["zastepstwo"] is True and zastepstwo["odwolana"] is False
    assert odwolana["odwolana"] is True and odwolana["zastepstwo"] is False
    assert zwykla["zastepstwo"] is False and zwykla["odwolana"] is False
    assert zwykla["info"] == ""


def test_przetworz_plan_deduplikuje_powtorzone_tygodnie():
    plan = przetworz_plan([tydzien(period()), tydzien(period())])

    assert len(plan) == 1


def test_nastepna_lekcja_zwraca_najblizsza_przyszla():
    plan = przetworz_plan(
        [
            tydzien(
                period(number=1, date_from="08:00", date_to="08:45"),
                period(number=2, date_from="09:00", date_to="09:45", subject="Fizyka"),
            )
        ]
    )

    wynik = nastepna_lekcja(plan, datetime(2026, 9, 7, 8, 50))

    assert wynik["przedmiot"] == "Fizyka"
    assert wynik["trwa_teraz"] is False
    assert wynik["za_minut"] == 10


def test_nastepna_lekcja_zwraca_trwajaca():
    plan = przetworz_plan([tydzien(period(date_from="08:00", date_to="08:45"))])

    wynik = nastepna_lekcja(plan, datetime(2026, 9, 7, 8, 30))

    assert wynik["trwa_teraz"] is True
    assert wynik["za_minut"] == 0


def test_nastepna_lekcja_pomija_odwolane():
    plan = przetworz_plan(
        [
            tydzien(
                period(number=1, date_from="08:00", info={"Lekcja odwołana": ""}),
                period(number=2, date_from="09:00", date_to="09:45", subject="Fizyka"),
            )
        ]
    )

    wynik = nastepna_lekcja(plan, datetime(2026, 9, 7, 7, 0))

    assert wynik["przedmiot"] == "Fizyka"


def test_nastepna_lekcja_brak_gdy_wszystko_minelo():
    plan = przetworz_plan([tydzien(period(date_from="08:00", date_to="08:45"))])

    assert nastepna_lekcja(plan, datetime(2026, 9, 7, 9, 0)) is None


def test_nastepna_lekcja_ignoruje_bledne_godziny():
    plan = przetworz_plan([tydzien(period(date_from="", date_to=""))])

    assert nastepna_lekcja(plan, datetime(2026, 9, 7, 7, 0)) is None


def test_lekcje_dnia_i_grupowanie():
    plan = przetworz_plan(
        [
            tydzien(
                period(date_="2026-09-07", number=1),
                period(date_="2026-09-07", number=2),
                period(date_="2026-09-08", number=1, weekday="Tuesday"),
            )
        ]
    )

    assert len(lekcje_dnia(plan, date(2026, 9, 7))) == 2
    assert lekcje_dnia(plan, date(2026, 9, 9)) == []

    dni = pogrupuj_wg_dni(plan)
    assert list(dni.keys()) == ["2026-09-07", "2026-09-08"]
    assert len(dni["2026-09-07"]) == 2


def _dwa_dni():
    """Plan na dzis (2 lekcje) i jutro (1 lekcja)."""
    return przetworz_plan(
        [
            tydzien(
                period(number=1, date_from="08:00", date_to="08:45"),
                period(number=2, date_from="09:00", date_to="09:45", subject="Fizyka"),
                period(
                    number=1, date_="2026-09-08", weekday="Tuesday",
                    date_from="08:00", date_to="08:45", subject="Historia",
                ),
            )
        ]
    )


def test_biezacy_dzien_pokazuje_dzis_w_trakcie_zajec():
    wynik = biezacy_dzien(_dwa_dni(), datetime(2026, 9, 7, 8, 30))

    assert [l["data"] for l in wynik] == ["2026-09-07"] * 2


def test_biezacy_dzien_pokazuje_dzis_az_do_konca_ostatniej_lekcji():
    # Minuta przed koncem ostatniej lekcji dzien nadal jest aktualny.
    wynik = biezacy_dzien(_dwa_dni(), datetime(2026, 9, 7, 9, 44))

    assert wynik[0]["data"] == "2026-09-07"


def test_biezacy_dzien_przechodzi_na_kolejny_po_ostatniej_lekcji():
    wynik = biezacy_dzien(_dwa_dni(), datetime(2026, 9, 7, 9, 46))

    assert [l["przedmiot"] for l in wynik] == ["Historia"]
    assert wynik[0]["data"] == "2026-09-08"


def test_biezacy_dzien_pusty_gdy_caly_plan_minal():
    assert biezacy_dzien(_dwa_dni(), datetime(2026, 9, 9, 0, 0)) == []


def test_dni_do_wyswietlenia_pomija_zakonczone():
    dni = dni_do_wyswietlenia(_dwa_dni(), datetime(2026, 9, 7, 9, 46))

    assert list(dni.keys()) == ["2026-09-08"]


def test_dni_do_wyswietlenia_zachowuje_dzien_bez_godzin():
    # Nie ukrywamy danych, ktorych nie da sie zinterpretowac.
    plan = przetworz_plan([tydzien(period(date_from="", date_to=""))])

    assert list(dni_do_wyswietlenia(plan, datetime(2026, 9, 9, 0, 0))) == ["2026-09-07"]


def _plan_dnia():
    """Trzy lekcje jednego dnia: fizyka jest lekcja nr 4."""
    return przetworz_plan(
        [
            tydzien(
                period(number=3, subject="matematyka"),
                period(number=4, subject="fizyka"),
                period(number=5, subject="historia"),
            )
        ]
    )


def _zdarzenie(**kw):
    baza = {
        "data": "2026-09-07",
        "tytul": "kartkówka",
        "przedmiot": "fizyka",
        "godzina": "unknown",
        "numer_lekcji": 4,
        "szczegoly": {"Nauczyciel": "Anna Nowak", "Opis": "wielkości fizyczne"},
    }
    baza.update(kw)
    return baza


def test_wydarzenie_przypina_sie_po_numerze_lekcji():
    plan, dnia, _ = polacz_z_wydarzeniami(_plan_dnia(), [_zdarzenie()])

    fizyka = next(l for l in plan if l["numer"] == 4)
    assert [w["tytul"] for w in fizyka["wydarzenia"]] == ["kartkówka"]
    assert fizyka["wydarzenia"][0]["opis"] == "wielkości fizyczne"
    assert dnia == {}
    # pozostale lekcje nietkniete
    assert all(not l["wydarzenia"] for l in plan if l["numer"] != 4)


def test_wydarzenie_przypina_sie_po_przedmiocie_gdy_brak_numeru():
    # Librus zwraca "unknown" zamiast numeru lekcji.
    plan, dnia, _ = polacz_z_wydarzeniami(
        _plan_dnia(), [_zdarzenie(numer_lekcji="unknown", przedmiot="Historia")]
    )

    historia = next(l for l in plan if l["numer"] == 5)
    assert len(historia["wydarzenia"]) == 1
    assert dnia == {}


def test_wydarzenie_bez_dopasowania_trafia_do_calodniowych():
    zdarzenie = _zdarzenie(
        numer_lekcji="unknown",
        tytul="godz.: 17:00",
        przedmiot="Wywiadówka: zebranie rodziców",
    )

    plan, dnia, _ = polacz_z_wydarzeniami(_plan_dnia(), [zdarzenie])

    assert all(not l["wydarzenia"] for l in plan)
    assert [w["przedmiot"] for w in dnia["2026-09-07"]] == ["Wywiadówka: zebranie rodziców"]


def test_wydarzenie_z_innego_dnia_jest_pomijane():
    plan, dnia, _ = polacz_z_wydarzeniami(_plan_dnia(), [_zdarzenie(data="2026-10-01")])

    assert all(not l["wydarzenia"] for l in plan)
    assert dnia == {}


def test_zadanie_przypina_sie_do_dnia_terminu():
    zadanie = {
        "przedmiot": "Matematyka",
        "kategoria": "Praca domowa",
        "termin": "2026-09-07",
        "nauczyciel": "Danuta Kowalska",
    }

    plan, _, zadania_dnia = polacz_z_wydarzeniami(_plan_dnia(), None, [zadanie])

    matematyka = next(l for l in plan if l["numer"] == 3)
    assert [z["kategoria"] for z in matematyka["zadania"]] == ["Praca domowa"]
    assert zadania_dnia == {}


def test_zadanie_toleruje_date_z_kropkami():
    zadanie = {"przedmiot": "fizyka", "kategoria": "Zadanie", "termin": "07.09.2026"}

    plan, _, _ = polacz_z_wydarzeniami(_plan_dnia(), None, [zadanie])

    assert len(next(l for l in plan if l["numer"] == 4)["zadania"]) == 1


def test_zadanie_bez_lekcji_z_przedmiotu_trafia_do_calodniowych():
    zadanie = {"przedmiot": "geografia", "kategoria": "Projekt", "termin": "2026-09-07"}

    plan, _, zadania_dnia = polacz_z_wydarzeniami(_plan_dnia(), None, [zadanie])

    assert all(not l["zadania"] for l in plan)
    assert [z["przedmiot"] for z in zadania_dnia["2026-09-07"]] == ["geografia"]


def test_polaczenie_bez_danych_nie_psuje_planu():
    plan, dnia, zadania_dnia = polacz_z_wydarzeniami(_plan_dnia(), None, None)

    assert len(plan) == 3
    assert all(l["wydarzenia"] == [] and l["zadania"] == [] for l in plan)
    assert dnia == {} and zadania_dnia == {}


def test_dni_do_wyswietlenia_ogranicza_liczbe_dni():
    plan = przetworz_plan(
        [
            tydzien(
                *[
                    period(date_=f"2026-09-{7 + i:02d}", number=1, date_from="08:00",
                           date_to="08:45", weekday="Monday")
                    for i in range(6)
                ]
            )
        ]
    )

    dni = dni_do_wyswietlenia(plan, datetime(2026, 9, 7, 7, 0), 5)

    assert len(dni) == 5
    assert list(dni)[0] == "2026-09-07"
    assert list(dni)[-1] == "2026-09-11"


def test_limit_liczony_po_odfiltrowaniu_zakonczonych_dni():
    """Zakonczony dzien nie zajmuje miejsca w limicie."""
    plan = przetworz_plan(
        [
            tydzien(
                *[
                    period(date_=f"2026-09-{7 + i:02d}", number=1, date_from="08:00",
                           date_to="08:45", weekday="Monday")
                    for i in range(6)
                ]
            )
        ]
    )

    # Po ostatniej lekcji 07.09 pierwszy dzien wypada, wiec dochodzi 12.09.
    dni = dni_do_wyswietlenia(plan, datetime(2026, 9, 7, 9, 0), 5)

    assert len(dni) == 5
    assert list(dni)[0] == "2026-09-08"
    assert list(dni)[-1] == "2026-09-12"
