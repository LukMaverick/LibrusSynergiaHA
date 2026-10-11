"""Testy metod klienta (async_get_timetable / schedule / homework) z zamockowana biblioteka."""

import asyncio
from datetime import date, datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

import _ha_stub
from _builders import tydzien
from _pure import load_package

pytestmark = pytest.mark.skipif(
    not _ha_stub.STUBBED, reason="testy z atrapami HA; prawdziwy HA ma wlasne testy"
)

pkg = load_package() if _ha_stub.STUBBED else None

from librus_apix.exceptions import ParseError, TokenError  # noqa: E402

PN = date(2026, 10, 12)


@pytest.fixture
def klient(monkeypatch):
    monkeypatch.setattr(pkg.dt_util, "now", lambda: datetime(2026, 10, 14, 10, 0, tzinfo=timezone.utc))
    k = pkg.LibrusApiClient("u", "p")
    k._client = MagicMock()
    k._token = "t"
    return k


def _tt(plan):
    return tydzien(PN, plan)


def test_timetable_dwa_tygodnie_i_ferie_jako_puste_dni(klient):
    wywolania = []

    def fake(client, monday):
        wywolania.append(monday.date())
        if monday.date() == PN:
            return _tt({0: {1: ("Matematyka", "", {})}})
        raise ParseError("brak planu")

    with patch("librus_apix.timetable.get_timetable", side_effect=fake):
        wynik = asyncio.run(klient.async_get_timetable(start=date(2026, 10, 14), weeks=2))
    assert wywolania == [PN, date(2026, 10, 19)]
    assert len(wynik["dni"]) == 14 and wynik["braki"] == []
    assert wynik["dni"]["2026-10-12"][0]["przedmiot"] == "Matematyka"
    assert wynik["dni"]["2026-10-20"] == []  # ferie -> puste dni, a nie blad
    assert wynik["godziny"]["1"] == "08:00–08:45"


def test_timetable_jeden_tydzien_pada_drugi_dziala(klient):
    def fake(client, monday):
        if monday.date() == PN:
            raise RuntimeError("zmiana HTML")
        return tydzien(monday.date(), {0: {1: ("Matematyka", "", {})}})

    with patch("librus_apix.timetable.get_timetable", side_effect=fake):
        wynik = asyncio.run(klient.async_get_timetable(start=PN, weeks=2))
    assert wynik["braki"] == ["2026-10-12"]
    assert "2026-10-19" in wynik["dni"]


def test_timetable_wszystkie_tygodnie_pada_zwraca_none(klient):
    with patch("librus_apix.timetable.get_timetable", side_effect=RuntimeError("x")):
        assert asyncio.run(klient.async_get_timetable(start=PN, weeks=2)) is None


def test_timetable_token_wygasl_ponowne_logowanie(klient):
    proby = {"n": 0}

    def fake(client, monday):
        proby["n"] += 1
        if proby["n"] == 1:
            raise TokenError("wygasl")
        return tydzien(monday.date(), {0: {1: ("Matematyka", "", {})}})

    async def fake_auth():
        klient._client, klient._token = MagicMock(), "nowy"
        return True

    klient.async_authenticate = fake_auth
    with patch("librus_apix.timetable.get_timetable", side_effect=fake):
        wynik = asyncio.run(klient.async_get_timetable(start=PN, weeks=1))
    assert wynik is not None and proby["n"] == 2


def _ev(tytul, przedmiot="Matematyka", numer=2):
    return SimpleNamespace(title=tytul, subject=przedmiot, hour="unknown", number=numer,
                           data={"Opis": "x"}, href="h")


def test_schedule_domyslnie_od_poniedzialku_tygodnia_i_pusty_miesiac(klient):
    zapytane = []

    def fake(client, month, year):
        zapytane.append((month, year))
        if month == "11":
            raise ParseError("brak zdarzen")
        # 9 pazdziernika (przed poniedzialkiem 12.) i 14 pazdziernika
        return {9: [_ev("Stary")], 14: [_ev("Sprawdzian")]}

    with patch("librus_apix.schedule.get_schedule", side_effect=fake):
        wynik = asyncio.run(klient.async_get_schedule())
    assert zapytane == [("10", "2026"), ("11", "2026")]
    assert [e["tytul"] for e in wynik] == ["Sprawdzian"]  # 9.10 poza zakresem, listopad pusty
    assert wynik[0]["data"] == "2026-10-14" and wynik[0]["numer_lekcji"] == 2


def test_schedule_zakres_przez_granice_miesiaca_i_roku(klient):
    zapytane = []

    def fake(client, month, year):
        zapytane.append((month, year))
        return {}

    with patch("librus_apix.schedule.get_schedule", side_effect=fake):
        asyncio.run(klient.async_get_schedule(od=date(2026, 12, 28), do=date(2027, 1, 3)))
    assert zapytane == [("12", "2026"), ("01", "2027")]


def test_homework_domyslny_zakres_i_parseerror_bez_halasu(klient):
    zakresy = []

    def fake(client, od, do):
        zakresy.append((od, do))
        return ["zadanie"]

    with patch("librus_apix.homework.get_homework", side_effect=fake):
        assert asyncio.run(klient.async_get_homework()) == ["zadanie"]
    assert zakresy == [("2026-10-07", "2026-11-13")]  # dzis-7 .. dzis+30

    with patch("librus_apix.homework.get_homework", side_effect=ParseError("pusto")):
        assert asyncio.run(klient.async_get_homework()) is None


def test_homework_detail(klient):
    with patch("librus_apix.homework.homework_detail", return_value={"Treść": "Ćw. 3"}) as m:
        assert asyncio.run(klient.async_get_homework_detail("z1")) == {"Treść": "Ćw. 3"}
        m.assert_called_once()
    with patch("librus_apix.homework.homework_detail", side_effect=RuntimeError("x")):
        assert asyncio.run(klient.async_get_homework_detail("z1")) is None
