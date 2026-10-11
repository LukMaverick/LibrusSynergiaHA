"""Testy logiki koordynatora, uslugi tygodnia i sensorow planu (z atrapami HA)."""

import asyncio
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

import _ha_stub
from _builders import fixture, homework, tydzien
from _pure import load, load_full

pytestmark = pytest.mark.skipif(
    not _ha_stub.STUBBED, reason="testy z atrapami HA; prawdziwy HA ma wlasne testy"
)

sensor = load_full("sensor") if _ha_stub.STUBBED else None
plan = load("plan")

PN = date(2026, 10, 12)  # poniedzialek
SRODA_10 = datetime(2026, 10, 14, 10, 0, tzinfo=timezone.utc)


def _plan_tygodnia(poniedzialek_tygodnia: date) -> dict:
    t = tydzien(poniedzialek_tygodnia, {
        0: {1: ("Matematyka", "Jan Kowalski - s. 12", {}), 2: ("Język polski", "", {})},
        2: {1: ("Biologia", "", {}), 2: ("Matematyka", "", {}), 3: ("Historia", "", {"Lekcja odwołana": ""})},
        4: {1: ("Angielski", "", {})},
    })
    return plan.normalizuj_tydzien(t)


class FakeClient:
    def __init__(self):
        self.wywolania = {"timetable": [], "detail": [], "schedule": [], "homework": []}
        self.timetable_ok = True
        self.homework = [homework(**h) for h in fixture("zadania.json")]
        self.homework_ok = True
        self.terminarz = fixture("terminarz_pulapki.json")

    async def async_get_student_information(self):
        return SimpleNamespace(name="Ola Kowalska", class_name="5A", number=7, tutor="X", school="Y", lucky_number=3)

    async def async_get_grades(self):
        return [{"subject": "Matematyka", "grade": "5", "date": "2026-10-01", "category": "T",
                 "teacher": "X", "semester": 2, "type": "numeric"}]

    async def async_get_messages(self, count=10):
        return []

    async def async_get_homework(self, od=None, do=None):
        self.wywolania["homework"].append((od, do))
        return self.homework if self.homework_ok else None

    async def async_get_homework_detail(self, href):
        self.wywolania["detail"].append(href)
        return {"Treść": f"Zrób zadanie {href}"}

    async def async_get_schedule(self, od=None, do=None):
        self.wywolania["schedule"].append((od, do))
        return self.terminarz

    async def async_get_timetable(self, start=None, weeks=2):
        self.wywolania["timetable"].append((start, weeks))
        if not self.timetable_ok:
            return None
        wynik = {"dni": {}, "godziny": {}, "braki": []}
        for i in range(weeks):
            czesc = _plan_tygodnia(plan.poniedzialek(start) + timedelta(weeks=i))
            wynik["dni"].update(czesc["dni"])
            wynik["godziny"].update(czesc["godziny"])
        return wynik


@pytest.fixture
def czas(monkeypatch):
    stan = {"now": SRODA_10}
    monkeypatch.setattr(sensor.dt_util, "now", lambda: stan["now"])
    return stan


@pytest.fixture
def koordynator(czas):
    _ha_stub.Store.wczytane = None
    hass = MagicMock()
    klient = FakeClient()
    k = sensor.LibrusDataUpdateCoordinator(hass, klient, SimpleNamespace(entry_id="e1"))
    return k, klient, hass


def odswiez(k):
    k.data = asyncio.run(k._async_update_data())
    return k.data


def test_pierwsze_odswiezenie_buduje_plan_zadania_i_nie_wysyla_zdarzen(koordynator):
    k, klient, hass = koordynator
    dane = odswiez(k)
    assert dane["plan_scalony"]["2026-10-14"]["przedmioty"] == ["Biologia", "Matematyka"]  # Historia odwolana
    assert dane["plan_scalony"]["2026-10-14"]["zakres"] == "08:00–09:40"
    assert len(dane["zadania_norm"]) == 5
    hass.bus.fire.assert_not_called()


def test_zadania_legacy_zachowuja_stare_klucze_i_pomijaja_zalegle(koordynator):
    k, _, _ = koordynator
    dane = odswiez(k)
    legacy = dane["zadania"]
    assert {z["przedmiot"] for z in legacy} == {"Matematyka", "Język angielski", "Historia"}  # bez Geografii (po terminie)
    z = next(x for x in legacy if x["przedmiot"] == "Język angielski")
    assert set(z) == {"przedmiot", "kategoria", "nauczyciel", "lekcja", "data_zadania", "termin", "termin_iso", "href"}
    assert z["termin"] == "16.10.2026" and z["termin_iso"] == "2026-10-16"


def test_tresci_pobierane_dla_nowych_zadan_z_limitem_i_cache(koordynator):
    k, klient, _ = koordynator
    dane = odswiez(k)
    # w horyzoncie 7 dni sa z1, z2 (14.10); angielski bez href, historia bez daty, geografia po terminie
    assert sorted(klient.wywolania["detail"]) == ["z1", "z2"]
    tresci = {z["id"]: z["tresc"] for z in dane["zadania_norm"]}
    assert tresci["z1"] == "Zrób zadanie z1"
    odswiez(k)
    assert sorted(klient.wywolania["detail"]) == ["z1", "z2"]  # bez ponownego pobierania
    assert k._store.zapisane == {"z1": "Zrób zadanie z1", "z2": "Zrób zadanie z2"}


def test_nowe_zadanie_wysyla_rozszerzone_zdarzenie(koordynator):
    k, klient, hass = koordynator
    odswiez(k)
    klient.homework.append(homework(subject="Fizyka", category="Zadanie domowe", teacher="X", lesson="1",
                                    task_date="2026-10-14", completion_date="2026-10-15", href="z9"))
    odswiez(k)
    wywolania = [c for c in hass.bus.fire.call_args_list if c.args[0] == sensor.EVENT_NOWE_ZADANIE]
    assert len(wywolania) == 1
    dane = wywolania[0].args[1]
    assert dane["przedmiot"] == "Fizyka" and dane["termin"] == "2026-10-15"
    assert dane["id"] == "z9" and dane["pilnosc"] == "jutro" and dane["dzien_tygodnia_terminu"] == "czwartek"
    assert dane["tresc"] == "Zrób zadanie z9"


def test_plan_jest_ograniczany_czasowo_i_odswiezany_po_zmianie_daty(koordynator, czas):
    k, klient, _ = koordynator
    odswiez(k)
    czas["now"] = SRODA_10 + timedelta(hours=1)
    odswiez(k)
    assert len(klient.wywolania["timetable"]) == 1
    czas["now"] = SRODA_10 + timedelta(hours=4)
    odswiez(k)
    assert len(klient.wywolania["timetable"]) == 2
    czas["now"] = SRODA_10 + timedelta(days=1)
    odswiez(k)
    assert len(klient.wywolania["timetable"]) == 3


def test_blad_planu_zachowuje_poprzednie_dane(koordynator, czas):
    k, klient, _ = koordynator
    odswiez(k)
    klient.timetable_ok = False
    czas["now"] = SRODA_10 + timedelta(days=1)
    dane = odswiez(k)
    assert k._plan_blad is True
    assert dane["plan_scalony"]["2026-10-14"]["liczba_lekcji"] == 2


def test_blad_zadan_zachowuje_dane_a_po_24h_zaklada_brak(koordynator, czas):
    k, klient, _ = koordynator
    odswiez(k)
    klient.homework_ok = False
    czas["now"] = SRODA_10 + timedelta(hours=2)
    assert len(odswiez(k)["zadania_norm"]) == 5
    assert k.data["zadania_aktualne"] is False
    czas["now"] = SRODA_10 + timedelta(hours=27)
    assert odswiez(k)["zadania_norm"] == []


def test_usluga_biezacy_tydzien_bez_zapytan_do_librusa(koordynator):
    k, klient, _ = koordynator
    odswiez(k)
    n_tt = len(klient.wywolania["timetable"])
    wynik = asyncio.run(k.async_pobierz_tydzien(date(2026, 10, 16)))
    assert wynik["tydzien_od"] == "2026-10-12" and wynik["tydzien_do"] == "2026-10-18"
    assert len(wynik["dni"]) == 7 and wynik["numery_lekcji"] == [1, 2, 3]
    assert wynik["nieaktualne"] is False
    nastepny = asyncio.run(k.async_pobierz_tydzien(date(2026, 10, 20)))
    assert nastepny["tydzien_od"] == "2026-10-19"
    assert len(klient.wywolania["timetable"]) == n_tt
    assert "nauczyciel" not in wynik["dni"][0]["lekcje"][0]  # kompaktowe


def test_usluga_poprzedni_tydzien_pobiera_i_cachuje(koordynator, czas):
    k, klient, _ = koordynator
    odswiez(k)
    wynik = asyncio.run(k.async_pobierz_tydzien(date(2026, 10, 7)))
    assert wynik["tydzien_od"] == "2026-10-05"
    assert klient.wywolania["timetable"][-1] == (date(2026, 10, 5), 1)
    n = len(klient.wywolania["timetable"])
    asyncio.run(k.async_pobierz_tydzien(date(2026, 10, 5)))
    assert len(klient.wywolania["timetable"]) == n  # z cache
    czas["now"] = SRODA_10 + timedelta(hours=2)  # po TTL
    asyncio.run(k.async_pobierz_tydzien(date(2026, 10, 5)))
    assert len(klient.wywolania["timetable"]) == n + 1


def test_usluga_poza_oknem_i_blad_pobierania(koordynator):
    k, klient, _ = koordynator
    odswiez(k)
    with pytest.raises(sensor.ServiceValidationError):
        asyncio.run(k.async_pobierz_tydzien(date(2026, 12, 21)))  # +10 tygodni
    with pytest.raises(sensor.ServiceValidationError):
        asyncio.run(k.async_pobierz_tydzien(date(2026, 8, 31)))
    klient.timetable_ok = False
    with pytest.raises(sensor.HomeAssistantError):
        asyncio.run(k.async_pobierz_tydzien(date(2026, 10, 5)))


def test_usluga_zwraca_cache_oznaczony_jako_nieaktualny_przy_bledzie(koordynator, czas):
    k, klient, _ = koordynator
    odswiez(k)
    asyncio.run(k.async_pobierz_tydzien(date(2026, 10, 5)))
    klient.timetable_ok = False
    czas["now"] = SRODA_10 + timedelta(hours=3)
    wynik = asyncio.run(k.async_pobierz_tydzien(date(2026, 10, 5)))
    assert wynik["nieaktualne"] is True


# ----------------------------------------------------------------------------- sensory


def _encje(koordynator):
    k, _, _ = koordynator
    odswiez(k)
    wpis = SimpleNamespace(entry_id="e1", options={}, data={"username": "ola"})
    return {
        "dzis": sensor.LibrusPlanDzisSensor(k, wpis, "ola", "Ola"),
        "jutro": sensor.LibrusPlanJutroSensor(k, wpis, "ola", "Ola"),
        "nastepna": sensor.LibrusNastepnaLekcjaSensor(k, wpis, "ola", "Ola"),
        "tydzien": sensor.LibrusPlanTygodniaSensor(k, wpis, "ola", "Ola"),
        "do_zrobienia": sensor.LibrusDoZrobieniaJutroSensor(k, wpis, "ola", "Ola"),
        "otwarte": sensor.LibrusZadaniaOtwarteSensor(k, wpis, "ola", "Ola"),
    }


def test_entity_id_i_unique_id_sa_jawne(koordynator):
    e = _encje(koordynator)
    assert e["dzis"].entity_id == "sensor.librus_ola_plan_dzis"
    assert e["tydzien"].entity_id == "sensor.librus_ola_plan_tygodnia"
    assert e["do_zrobienia"].entity_id == "sensor.librus_ola_do_zrobienia_jutro"
    assert e["otwarte"]._attr_unique_id == "e1_zadania_otwarte"


def test_plan_dzis_i_jutro_w_srode(koordynator):
    e = _encje(koordynator)
    assert e["dzis"].native_value == "08:00–09:40"
    assert e["dzis"].extra_state_attributes["przedmioty"] == ["Biologia", "Matematyka"]
    assert e["jutro"].native_value == "Wolne" or e["jutro"].extra_state_attributes["data"] == "2026-10-16"
    # czwartek (15.10) nie ma lekcji -> najblizszy dzien nauki to piatek
    assert e["jutro"].extra_state_attributes["data"] == "2026-10-16"
    assert e["jutro"].extra_state_attributes["czy_jutro"] is False


def test_plan_jutro_w_piatek_to_poniedzialek(koordynator, czas):
    czas["now"] = datetime(2026, 10, 16, 12, 0, tzinfo=timezone.utc)
    e = _encje(koordynator)
    a = e["jutro"].extra_state_attributes
    assert a["data"] == "2026-10-19" and a["dzien"] == "poniedziałek" and a["czy_jutro"] is False


def test_nastepna_lekcja_w_ciagu_dnia(koordynator, czas):
    e = _encje(koordynator)
    czas["now"] = datetime(2026, 10, 14, 7, 0, tzinfo=timezone.utc)
    assert e["nastepna"].native_value == "Biologia" and e["nastepna"].extra_state_attributes["trwa"] is False
    czas["now"] = datetime(2026, 10, 14, 8, 30, tzinfo=timezone.utc)
    assert e["nastepna"].native_value == "Biologia" and e["nastepna"].extra_state_attributes["trwa"] is True
    czas["now"] = datetime(2026, 10, 14, 8, 50, tzinfo=timezone.utc)
    assert e["nastepna"].native_value == "Matematyka"
    czas["now"] = datetime(2026, 10, 14, 12, 0, tzinfo=timezone.utc)
    assert e["nastepna"].native_value == "Koniec lekcji"  # trzecia lekcja jest odwolana
    czas["now"] = datetime(2026, 10, 15, 9, 0, tzinfo=timezone.utc)
    assert e["nastepna"].native_value == "Brak lekcji"


def test_plan_tygodnia_domyslnie_najblizszy_tydzien_nauki(koordynator, czas):
    e = _encje(koordynator)
    a = e["tydzien"].extra_state_attributes
    assert e["tydzien"].native_value == "12.10–18.10"
    assert a["entry_id"] == "e1" and a["tryb"] == "auto" and a["wersja_integracji"] == "1.3.0"
    czas["now"] = datetime(2026, 10, 17, 9, 0, tzinfo=timezone.utc)  # sobota
    assert e["tydzien"].native_value == "19.10–25.10"
    assert e["tydzien"].extra_state_attributes["dni"][0]["lekcje"][0]["przedmiot"] == "Matematyka"


def test_do_zrobienia_i_zadania_otwarte(koordynator, czas):
    e = _encje(koordynator)
    czas["now"] = datetime(2026, 10, 13, 18, 0, tzinfo=timezone.utc)  # wtorek wieczor, jutro = sroda 14.10
    # wtorek nie ma lekcji -> najblizszy dzien nauki to sroda 14.10 (termin dwoch zadan z matematyki)
    d = e["do_zrobienia"].extra_state_attributes
    assert d["data"] == "2026-10-14"
    assert len(d["zadania"]) == 2 and d["przedmioty_do_spakowania"] == ["Biologia", "Matematyka"]
    assert e["do_zrobienia"].native_value == 2
    o = e["otwarte"].extra_state_attributes
    assert o["liczba_dzis"] == 0 and o["liczba_jutro"] == 2 and len(o["po_terminie"]) == 1
    assert e["otwarte"].native_value == 4  # 2 mat + angielski + historia bez daty (otwarte)


def test_terminarz_sensor_pokazuje_tylko_przyszle(koordynator, czas):
    k, _, _ = koordynator
    odswiez(k)
    wpis = SimpleNamespace(entry_id="e1", options={}, data={})
    czas["now"] = datetime(2026, 10, 16, 8, 0, tzinfo=timezone.utc)
    s = sensor.LibrusTerminarzSensor(k, wpis)
    assert {z["data"] for z in s.extra_state_attributes["zdarzenia"]} == {"2026-10-16"}
