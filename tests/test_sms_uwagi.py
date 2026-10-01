"""Testy bramki SMS, uwag, opcji i akcji librus_apix.wyslij_sms."""

import asyncio
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from urllib.parse import parse_qs, urlsplit

import pytest
from aiohttp import web
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)

pytestmark = pytest.mark.enable_socket

from custom_components.librus_apix.const import (
    CONF_SCAN_INTERVAL,
    CONF_SMS_ENABLED,
    CONF_SMS_TEKST_OCENY,
    CONF_SMS_TEKST_UWAGI,
    CONF_SMS_URL_OCENY,
    CONF_SMS_URL_UWAGI,
    CONF_SMS_VERIFY_SSL,
    DOMAIN,
)
from custom_components.librus_apix.sms import podziel_adresy, waliduj_adresy, zbuduj_tekst, zbuduj_url
from custom_components.librus_apix.uwagi import parsuj_uwagi


# --------------------------------------------------------------- czyste funkcje

def test_zbuduj_url_koduje_wartosci():
    url = zbuduj_url(
        "https://sms.example.pl/send?code=a=b&przedmiot=%przedmiot%&ocena=%ocena%&konto=Max",
        {"przedmiot": "Język polski", "ocena": "4+"},
    )
    assert url == "https://sms.example.pl/send?code=a=b&przedmiot=J%C4%99zyk%20polski&ocena=4%2B&konto=Max"


def test_zbuduj_tekst_i_placeholder_tekst():
    dane = {"uczen": "Max K", "ocena": "5", "przedmiot": "Matematyka", "kategoria": "Sprawdzian"}
    dane["tekst"] = zbuduj_tekst("Librus %uczen%: nowa ocena %ocena% z %przedmiot% (%kategoria%)", dane)
    assert dane["tekst"] == "Librus Max K: nowa ocena 5 z Matematyka (Sprawdzian)"
    url = zbuduj_url("https://www.example.pl/smsgateway/48600000000?text=%tekst%", dane)
    assert url == "https://www.example.pl/smsgateway/48600000000?text=Librus%20Max%20K%3A%20nowa%20ocena%205%20z%20Matematyka%20%28Sprawdzian%29"


def test_podziel_i_waliduj_adresy():
    tekst = "https://a.pl/x?t=%tekst%\n\n# komentarz\n  http://b.pl/y  \nftp://zly\nbez-schematu"
    assert podziel_adresy(tekst) == ["https://a.pl/x?t=%tekst%", "http://b.pl/y", "ftp://zly", "bez-schematu"]
    assert waliduj_adresy(tekst) == ["ftp://zly", "bez-schematu"]
    assert podziel_adresy(None) == []


HTML_NAGLOWEK = """
<html><body><h2 class="inside">Uwagi</h2>
<table class="decorated big center">
 <thead><tr><td>Data</td><td>Nauczyciel</td><td>Rodzaj</td><td>Kategoria</td><td>Treść</td></tr></thead>
 <tbody>
  <tr class="line0"><td>2026-09-29</td><td>Jan Kowalski</td><td>uwaga</td><td>Zachowanie</td><td>Rozmawiał na lekcji</td></tr>
  <tr class="line1"><td>2026-09-30</td><td>Anna Nowak</td><td>pochwała</td><td>Aktywność</td><td>Pomógł koledze</td></tr>
 </tbody>
</table></body></html>
"""

HTML_KLUCZ_WARTOSC = """
<html><body>
<table class="decorated"><tr><th>Data</th><td>30.09.2026</td></tr><tr><th>Nauczyciel</th><td>Anna Nowak</td></tr>
<tr><th>Rodzaj</th><td>pochwała</td></tr><tr><th>Treść</th><td>Świetna prezentacja</td></tr></table>
</body></html>
"""


def test_parsuj_uwagi_tabela_z_naglowkiem():
    uwagi = parsuj_uwagi(HTML_NAGLOWEK)
    assert len(uwagi) == 2
    assert uwagi[0]["nauczyciel"] == "Jan Kowalski"
    assert uwagi[0]["tresc"] == "Rozmawiał na lekcji"
    assert uwagi[1]["rodzaj"] == "pochwała"
    assert uwagi[0]["id"] != uwagi[1]["id"]


def test_parsuj_uwagi_klucz_wartosc():
    uwagi = parsuj_uwagi(HTML_KLUCZ_WARTOSC)
    assert len(uwagi) == 1
    assert uwagi[0]["data"] == "30.09.2026"
    assert uwagi[0]["tresc"] == "Świetna prezentacja"


# ------------------------------------------------------------- lokalna bramka

@pytest.fixture
async def bramka(aiohttp_server):
    """Lokalny serwer HTTP udajacy bramke SMS - zapisuje otrzymane zadania."""
    odebrane = []

    async def handler(request):
        odebrane.append(str(request.rel_url))
        return web.Response(text="OK")

    app = web.Application()
    app.router.add_get("/{tail:.*}", handler)
    server = await aiohttp_server(app)
    return SimpleNamespace(url=f"http://127.0.0.1:{server.port}", odebrane=odebrane)


def _mock_client(grades, uwagi):
    client = MagicMock()
    client.async_authenticate = AsyncMock(return_value=True)
    client.async_get_grades = AsyncMock(side_effect=lambda: list(grades))
    client.async_get_messages = AsyncMock(return_value=[])
    client.async_get_homework = AsyncMock(return_value=[])
    client.async_get_schedule = AsyncMock(return_value=[])
    client.async_get_uwagi = AsyncMock(side_effect=lambda: list(uwagi))
    client.averages = {"Matematyka": {1: 4.2, 2: 3.9}}
    client.async_get_student_information = AsyncMock(
        return_value=SimpleNamespace(name="Max Kowalski", class_name="5a", number=7, tutor="X", school="SP", lucky_number=3)
    )
    return client


OCENA1 = {"subject": "Matematyka", "grade": "4", "date": "2026-09-20", "category": "Kartkówka", "teacher": "J. K.", "type": "numeric"}
OCENA2 = {"subject": "Język polski", "grade": "5+", "date": "2026-09-30", "category": "Sprawdzian", "teacher": "A. N.", "type": "numeric"}
UWAGA1 = {"id": "u1", "data": "2026-09-10", "nauczyciel": "J. K.", "rodzaj": "uwaga", "kategoria": "Zachowanie", "tresc": "Spóźnienie"}
UWAGA2 = {"id": "u2", "data": "2026-09-30", "nauczyciel": "A. N.", "rodzaj": "pochwała", "kategoria": "Aktywność", "tresc": "Pomógł koledze"}


async def _setup(hass: HomeAssistant, options, grades, uwagi):
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"username": "u", "password": "p"},
        options=options,
        entry_id="test_entry",
    )
    entry.add_to_hass(hass)
    client = _mock_client(grades, uwagi)
    # patch zostaje aktywny do konca testu (przeladowanie wpisu po zmianie opcji tez uzywa mocka)
    patch("custom_components.librus_apix.LibrusApiClient", return_value=client).start()
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry, client


@pytest.fixture(autouse=True)
def _zatrzymaj_patche():
    yield
    patch.stopall()


async def _odswiez(hass: HomeAssistant, minuty: int):
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=minuty + 1))
    await hass.async_block_till_done()
    await asyncio.sleep(0.05)  # zadania SMS
    await hass.async_block_till_done()


async def test_nowa_ocena_i_uwaga_wysyla_sms_na_wiele_hostow(hass: HomeAssistant, bramka):
    """Nowa ocena/uwaga -> zdarzenie HA + GET na kazdy adres z pola wieloliniowego."""
    grades = [OCENA1]
    uwagi = [UWAGA1]
    options = {
        CONF_SCAN_INTERVAL: 60,
        CONF_SMS_ENABLED: True,
        CONF_SMS_VERIFY_SSL: False,
        CONF_SMS_URL_OCENY: f"{bramka.url}/smsgateway/48600000001?text=%tekst%\n{bramka.url}/send?p=%przedmiot%&o=%ocena%&konto=Max",
        CONF_SMS_TEKST_OCENY: "Nowa ocena %ocena% z %przedmiot% (%kategoria%) - %uczen%",
        CONF_SMS_URL_UWAGI: f"{bramka.url}/smsgateway/48600000001?text=%tekst%",
        CONF_SMS_TEKST_UWAGI: "Uwaga (%rodzaj%) od %nauczyciel%: %tresc%",
    }
    zdarzenia = []
    hass.bus.async_listen("librus_apix_nowa_ocena", lambda e: zdarzenia.append(("ocena", e.data)))
    hass.bus.async_listen("librus_apix_nowa_uwaga", lambda e: zdarzenia.append(("uwaga", e.data)))

    entry, client = await _setup(hass, options, grades, uwagi)

    # sensory
    assert hass.states.get("sensor.uwagi").state == "1"
    assert hass.states.get("sensor.ostatnia_nowa_ocena").state == "4"
    assert hass.states.get("sensor.ostatnia_nowa_ocena").attributes["przedmiot"] == "Matematyka"

    # pierwsze pobranie: nic nie wysylamy
    assert bramka.odebrane == []
    assert zdarzenia == []

    # drugie pobranie bez zmian: nadal nic
    await _odswiez(hass, 60)
    assert bramka.odebrane == []

    # pojawia sie nowa ocena i nowa uwaga
    grades.append(OCENA2)
    uwagi.append(UWAGA2)
    await _odswiez(hass, 60)

    assert [z[0] for z in zdarzenia] == ["ocena", "uwaga"]
    assert zdarzenia[0][1]["ocena"] == "5+"
    assert zdarzenia[0][1]["uczen"] == "Max Kowalski"

    # wysylki ida rownolegle - porownujemy bez kolejnosci
    assert len(bramka.odebrane) == 3, bramka.odebrane
    zapytania = [(urlsplit(u).path, parse_qs(urlsplit(u).query)) for u in bramka.odebrane]
    assert ("/smsgateway/48600000001", {"text": ["Nowa ocena 5+ z Język polski (Sprawdzian) - Max Kowalski"]}) in zapytania
    assert ("/send", {"p": ["Język polski"], "o": ["5+"], "konto": ["Max"]}) in zapytania
    assert ("/smsgateway/48600000001", {"text": ["Uwaga (pochwała) od A. N.: Pomógł koledze"]}) in zapytania

    # sensory "ostatnia nowa"
    st = hass.states.get("sensor.ostatnia_nowa_ocena")
    assert st.state == "5+" and st.attributes["przedmiot"] == "Język polski"
    st = hass.states.get("sensor.ostatnia_nowa_uwaga")
    assert st.state == "Pomógł koledze" and st.attributes["rodzaj"] == "pochwała"
    assert hass.states.get("sensor.oceny").attributes["ostatnia_nowa_ocena_przedmiot"] == "Język polski"

    # magazyn HA zapisany -> po "restarcie" (nowy wpis z tym samym entry_id) brak duplikatow,
    # ale ocena dodana w czasie przestoju zostanie wykryta
    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    bramka.odebrane.clear()
    zdarzenia.clear()
    grades.append({**OCENA1, "grade": "3", "date": "2026-10-01"})
    entry2, _ = await _setup(hass, options, grades, uwagi)
    await asyncio.sleep(0.05)
    await hass.async_block_till_done()
    assert [z[1].get("ocena", z[1].get("tresc")) for z in zdarzenia] == ["3"], zdarzenia
    assert len(bramka.odebrane) == 2  # tylko nowa ocena, na 2 adresy; brak duplikatu 5+ i uwagi


async def test_sms_wylaczony_tylko_zdarzenia(hass: HomeAssistant, bramka):
    grades = [OCENA1]
    options = {CONF_SMS_ENABLED: False, CONF_SMS_URL_OCENY: f"{bramka.url}/x?text=%tekst%"}
    zdarzenia = []
    hass.bus.async_listen("librus_apix_nowa_ocena", lambda e: zdarzenia.append(e.data))
    await _setup(hass, options, grades, [])
    grades.append(OCENA2)
    await _odswiez(hass, 120)
    assert len(zdarzenia) == 1
    assert bramka.odebrane == []


async def test_akcja_wyslij_sms(hass: HomeAssistant, bramka):
    options = {
        CONF_SMS_ENABLED: True,
        CONF_SMS_URL_OCENY: f"{bramka.url}/g?text=%tekst%",
        CONF_SMS_TEKST_OCENY: "%uczen%: %ocena% z %przedmiot%",
    }
    await _setup(hass, options, [OCENA1], [])
    assert hass.services.has_service(DOMAIN, "wyslij_sms")

    await hass.services.async_call(
        DOMAIN, "wyslij_sms", {"typ": "ocena", "ocena": "5", "przedmiot": "Fizyka"}, blocking=True
    )
    assert parse_qs(urlsplit(bramka.odebrane[-1]).query)["text"] == ["Max Kowalski: 5 z Fizyka"]

    # wlasny adres + gotowy tekst
    await hass.services.async_call(
        DOMAIN, "wyslij_sms",
        {"url": f"{bramka.url}/inny?t=%tekst%&typ=%typ%", "tekst": "Test 123", "typ": "uwaga"},
        blocking=True,
    )
    assert parse_qs(urlsplit(bramka.odebrane[-1]).query) == {"t": ["Test 123"], "typ": ["uwaga"]}


async def test_options_flow(hass: HomeAssistant):
    entry, _ = await _setup(hass, {}, [OCENA1], [])
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] == "form" and result["step_id"] == "init"

    # bledny adres
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_SMS_ENABLED: True, CONF_SMS_URL_OCENY: "sms.example.pl/x"}
    )
    assert result["type"] == "form" and result["errors"] == {"base": "sms_url_invalid"}

    # wlaczone bez adresow
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_SMS_ENABLED: True}
    )
    assert result["errors"] == {"base": "sms_url_required"}

    # poprawnie
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            CONF_SCAN_INTERVAL: 60,
            CONF_SMS_ENABLED: True,
            CONF_SMS_VERIFY_SSL: False,
            CONF_SMS_URL_OCENY: "https://sms.example.pl/smsgateway/48600000000?text=%tekst%\nhttps://b.pl/x",
        },
    )
    assert result["type"] == "create_entry"
    await hass.async_block_till_done()
    assert entry.options[CONF_SMS_URL_OCENY].startswith("https://sms.example.pl")
    assert entry.options[CONF_SMS_VERIFY_SSL] is False
    assert entry.options[CONF_SCAN_INTERVAL] == 60


# ------------------------------------------------- metody POST / push / przycisk

@pytest.fixture
async def bramka2(aiohttp_server):
    """Bramka zapisujaca metode, sciezke, query i body."""
    odebrane = []

    async def handler(request):
        body = await request.text()
        odebrane.append({
            "method": request.method,
            "path": request.path,
            "query": dict(request.query),
            "body": body,
            "ctype": request.content_type,
        })
        return web.Response(text="OK")

    app = web.Application()
    app.router.add_route("*", "/{tail:.*}", handler)
    server = await aiohttp_server(app)
    return SimpleNamespace(url=f"http://127.0.0.1:{server.port}", odebrane=odebrane)


async def test_metody_post_i_post_json(hass: HomeAssistant, bramka2):
    from custom_components.librus_apix.const import CONF_SMS_METHOD
    import json as _json

    options = {
        CONF_SMS_ENABLED: True,
        CONF_SMS_METHOD: "post",
        CONF_SMS_URL_OCENY: f"{bramka2.url}/smsgateway/48600000000?text=%tekst%&ocena=%ocena%",
        CONF_SMS_TEKST_OCENY: "Ocena %ocena% z %przedmiot%",
    }
    entry, _ = await _setup(hass, options, [OCENA1], [])
    await hass.services.async_call(DOMAIN, "wyslij_sms", {"ocena": "4+", "przedmiot": "Fizyka"}, blocking=True)
    z = bramka2.odebrane[-1]
    assert z["method"] == "POST" and z["path"] == "/smsgateway/48600000000"
    assert z["query"] == {}
    assert z["ctype"] == "application/x-www-form-urlencoded"
    assert parse_qs(z["body"]) == {"text": ["Ocena 4+ z Fizyka"], "ocena": ["4+"]}

    # POST JSON przez opcje
    hass.config_entries.async_update_entry(entry, options={**options, CONF_SMS_METHOD: "post_json"})
    await hass.async_block_till_done()
    await hass.services.async_call(DOMAIN, "wyslij_sms", {"ocena": "3", "przedmiot": "Chemia"}, blocking=True)
    z = bramka2.odebrane[-1]
    assert z["method"] == "POST" and z["ctype"] == "application/json"
    assert _json.loads(z["body"]) == {"text": "Ocena 3 z Chemia", "ocena": "3"}

    # GET (domyslnie)
    hass.config_entries.async_update_entry(entry, options={**options, CONF_SMS_METHOD: "get"})
    await hass.async_block_till_done()
    await hass.services.async_call(DOMAIN, "wyslij_sms", {"ocena": "2", "przedmiot": "Biologia"}, blocking=True)
    z = bramka2.odebrane[-1]
    assert z["method"] == "GET" and z["query"] == {"text": "Ocena 2 z Biologia", "ocena": "2"}


async def test_push_i_przycisk_testowy(hass: HomeAssistant, bramka2):
    from custom_components.librus_apix.const import CONF_PUSH_NOTIFY
    from homeassistant.exceptions import HomeAssistantError

    pushe = []
    hass.services.async_register("notify", "mobile_app_test", lambda call: pushe.append(dict(call.data)))

    # brak kanalow -> przycisk zglasza blad
    entry, _ = await _setup(hass, {}, [OCENA1], [])
    assert hass.states.get("button.test_powiadomien_ocena") is not None
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            "button", "press", {"entity_id": "button.test_powiadomien_ocena"}, blocking=True
        )

    options = {
        CONF_SMS_ENABLED: True,
        CONF_SMS_URL_OCENY: f"{bramka2.url}/g?text=%tekst%",
        CONF_PUSH_NOTIFY: "notify.mobile_app_test\nmobile_app_nieistniejacy",
    }
    hass.config_entries.async_update_entry(entry, options=options)
    await hass.async_block_till_done()

    await hass.services.async_call(
        "button", "press", {"entity_id": "button.test_powiadomien_ocena"}, blocking=True
    )
    await hass.async_block_till_done()
    assert bramka2.odebrane[-1]["query"]["text"].startswith("Librus Max Kowalski: nowa ocena 5 z Test (przedmiot)")
    assert len(pushe) == 1 and pushe[0]["title"] == "🎓 Librus: nowa ocena 5"
    assert "Test (przedmiot)" in pushe[0]["message"]

    # prawdziwa nowa uwaga -> push (bez adresow SMS dla uwag -> tylko push)
    pushe.clear()
    grades = [OCENA1]
    uwagi = [UWAGA1]
    await hass.config_entries.async_unload(entry.entry_id)
    entry2, _ = await _setup(hass, options, grades, uwagi)
    uwagi.append(UWAGA2)
    await _odswiez(hass, 120)
    # magazyn z poprzedniego wpisu (ten sam entry_id) nie znal zadnych uwag -> obie sa "nowe"
    assert len(pushe) == 2 and all(p["title"] == "⚠️ Librus: nowa uwaga" for p in pushe)
    assert "Pomógł koledze" in pushe[-1]["message"]


# ------------------------------------------------- waga, komentarz, srednia

def test_srednia_wazona():
    from custom_components.librus_apix.coordinator import _srednia_ocen
    oceny = [
        {"ocena": "5", "waga": 3, "liczy_do_sredniej": True},
        {"ocena": "3", "waga": 1, "liczy_do_sredniej": True},
        {"ocena": "1", "waga": 5, "liczy_do_sredniej": False},  # pomijana
        {"ocena": "np", "waga": 2},  # nie-liczba
    ]
    assert _srednia_ocen(oceny) == 4.5  # (5*3 + 3*1) / 4
    # brak wag -> zwykla srednia
    assert _srednia_ocen([{"ocena": "4+"}, {"ocena": "3-"}]) == 3.62


def test_opis_na_slownik():
    from custom_components.librus_apix import _opis_na_slownik
    d = _opis_na_slownik("Ocena: 5\nPrzedmiot: Fizyka\nKategoria: Sprawdzian\nWaga: 3\nLicz do średniej: tak\nKomentarz: Bardzo dobrze: brawo\nDodał: X")
    assert d["Komentarz"] == "Bardzo dobrze: brawo" and d["Waga"] == "3"


async def test_nowa_ocena_z_waga_i_komentarzem(hass: HomeAssistant, bramka2):
    grades = [
        {**OCENA1, "weight": 1, "counts": True, "comment": ""},
    ]
    options = {
        CONF_SMS_ENABLED: True,
        CONF_SMS_URL_OCENY: f"{bramka2.url}/g?text=%tekst%&waga=%waga%&srednia=%srednia%",
        CONF_SMS_TEKST_OCENY: "%ocena% z %przedmiot% (waga %waga%) srednia %srednia% %komentarz%",
    }
    zdarzenia = []
    hass.bus.async_listen("librus_apix_nowa_ocena", lambda e: zdarzenia.append(e.data))
    await _setup(hass, options, grades, [])
    assert hass.states.get("sensor.srednia_matematyka").state == "4.0"
    assert hass.states.get("sensor.srednia_matematyka").attributes["srednia_librus"] in (4.2, 3.9)

    grades.append({**OCENA1, "grade": "5", "date": "2026-10-02", "weight": 3, "counts": True, "comment": "Super praca"})
    await _odswiez(hass, 120)

    assert zdarzenia[0]["waga"] == 3 and zdarzenia[0]["komentarz"] == "Super praca"
    assert zdarzenia[0]["srednia"] == 4.75  # (4*1 + 5*3) / 4
    q = bramka2.odebrane[-1]["query"]
    assert q == {"text": "5 z Matematyka (waga 3) srednia 4.75 Super praca", "waga": "3", "srednia": "4.75"}
    assert hass.states.get("sensor.srednia_matematyka").state == "4.75"
    st = hass.states.get("sensor.ostatnia_nowa_ocena")
    assert st.attributes["waga"] == 3 and st.attributes["komentarz"] == "Super praca" and st.attributes["srednia"] == 4.75
    oceny = hass.states.get("sensor.matematyka").attributes["oceny"]
    assert oceny[-1]["komentarz"] == "Super praca" and oceny[-1]["waga"] == 3


# ------------------------------------------------- test z formularza opcji

async def test_options_flow_wyslij_test(hass: HomeAssistant, bramka2):
    from custom_components.librus_apix.const import CONF_WYSLIJ_TEST
    entry, _ = await _setup(hass, {}, [OCENA1], [])
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            CONF_SMS_ENABLED: True,
            CONF_SMS_URL_OCENY: f"{bramka2.url}/g?text=%tekst%\n{bramka2.url}/h?o=%ocena%",
            CONF_SMS_TEKST_OCENY: "TEST %ocena% %przedmiot% %uczen%",
            CONF_WYSLIJ_TEST: True,
        },
    )
    # krok z wynikiem testu, jeszcze nic nie zapisane
    assert result["type"] == "form" and result["step_id"] == "test"
    assert result["description_placeholders"]["sms_ok"] == "2"
    assert result["description_placeholders"]["sms_all"] == "2"
    assert CONF_SMS_URL_OCENY not in entry.options
    teksty = [z["query"] for z in bramka2.odebrane]
    assert {"text": "TEST 5 Test (przedmiot) Max Kowalski"} in teksty and {"o": "5"} in teksty

    # 'Przeslij' zapisuje (bez flagi testu)
    result = await hass.config_entries.options.async_configure(result["flow_id"], {})
    assert result["type"] == "create_entry"
    await hass.async_block_till_done()
    assert entry.options[CONF_SMS_URL_OCENY].startswith(bramka2.url)
    assert CONF_WYSLIJ_TEST not in entry.options


# ------------------------------------------------- naglowki HTTP / basic auth

def test_parsuj_i_waliduj_naglowki():
    from custom_components.librus_apix.sms import parsuj_naglowki, waliduj_naglowki
    tekst = "Authorization: Bearer abc:def\n# komentarz\nX-Api-Key:  klucz  \nzla linia\n: pusta"
    assert parsuj_naglowki(tekst) == {"Authorization": "Bearer abc:def", "X-Api-Key": "klucz"}
    assert waliduj_naglowki(tekst) == ["zla linia", ": pusta"]


async def test_naglowki_i_basic_auth(hass: HomeAssistant, aiohttp_server):
    from custom_components.librus_apix.const import CONF_SMS_HEADERS, CONF_SMS_METHOD
    import base64

    odebrane = []

    async def handler(request):
        odebrane.append({"headers": dict(request.headers), "body": await request.text(), "method": request.method})
        return web.Response(text="OK")

    app = web.Application()
    app.router.add_route("*", "/{tail:.*}", handler)
    server = await aiohttp_server(app)

    options = {
        CONF_SMS_ENABLED: True,
        CONF_SMS_METHOD: "post",
        CONF_SMS_HEADERS: "Authorization: Bearer token123\nX-Api-Key: k1",
        CONF_SMS_URL_OCENY: f"http://127.0.0.1:{server.port}/Messages.json?To=%2B48600000000&Body=%tekst%",
        CONF_SMS_TEKST_OCENY: "%ocena% z %przedmiot%",
    }
    entry, _ = await _setup(hass, options, [OCENA1], [])
    await hass.services.async_call(DOMAIN, "wyslij_sms", {"ocena": "5", "przedmiot": "Fizyka"}, blocking=True)
    z = odebrane[-1]
    assert z["method"] == "POST"
    assert z["headers"]["Authorization"] == "Bearer token123" and z["headers"]["X-Api-Key"] == "k1"
    assert parse_qs(z["body"]) == {"To": ["+48600000000"], "Body": ["5 z Fizyka"]}

    # Basic auth w adresie (jak Twilio: SID:TOKEN@host)
    hass.config_entries.async_update_entry(entry, options={
        **options, CONF_SMS_HEADERS: "",
        CONF_SMS_URL_OCENY: f"http://ACsid:sekret@127.0.0.1:{server.port}/Messages.json?Body=%tekst%",
    })
    await hass.async_block_till_done()
    await hass.services.async_call(DOMAIN, "wyslij_sms", {"ocena": "4", "przedmiot": "Chemia"}, blocking=True)
    z = odebrane[-1]
    oczekiwany = "Basic " + base64.b64encode(b"ACsid:sekret").decode()
    assert z["headers"]["Authorization"] == oczekiwany
    assert "X-Api-Key" not in z["headers"]


async def test_options_flow_naglowki_blad(hass: HomeAssistant):
    from custom_components.librus_apix.const import CONF_SMS_HEADERS
    entry, _ = await _setup(hass, {}, [OCENA1], [])
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_SMS_HEADERS: "Authorization Bearer x"}
    )
    assert result["type"] == "form" and result["errors"] == {"base": "sms_headers_invalid"}


# ------------------------------------------------- dwie pory sprawdzania

def test_oblicz_interwal():
    from datetime import datetime
    from custom_components.librus_apix.coordinator import oblicz_interwal
    from custom_components.librus_apix.const import (
        CONF_SCAN_INTERVAL, CONF_SCAN_INTERVAL_SZKOLA, CONF_SZKOLA_OD, CONF_SZKOLA_DO, CONF_SZKOLA_DNI_ROBOCZE,
    )
    opcje = {CONF_SCAN_INTERVAL: 180, CONF_SCAN_INTERVAL_SZKOLA: 55, CONF_SZKOLA_OD: "07:00:00", CONF_SZKOLA_DO: "15:00:00"}
    sroda = datetime(2026, 9, 30)  # sroda

    # w szkole
    i, tryb = oblicz_interwal(opcje, sroda.replace(hour=9, minute=10))
    assert (i, tryb) == (timedelta(minutes=55), "szkola")
    # granica: 07:00 -> szkola, 15:00 -> poza
    assert oblicz_interwal(opcje, sroda.replace(hour=7))[1] == "szkola"
    assert oblicz_interwal(opcje, sroda.replace(hour=15))[1] == "poza_szkola"
    # po szkole: pelne 180 min (do jutra 07:00 daleko)
    assert oblicz_interwal(opcje, sroda.replace(hour=16)) == (timedelta(minutes=180), "poza_szkola")
    # noc 05:00 -> dociagniecie do 07:00 (2h zamiast 3h)
    assert oblicz_interwal(opcje, sroda.replace(hour=5)) == (timedelta(hours=2), "poza_szkola")
    # weekend (sobota 10:00) -> poza szkola, pelne 180 min (do poniedzialku daleko)
    sobota = datetime(2026, 10, 3, 10, 0)
    assert oblicz_interwal(opcje, sobota) == (timedelta(minutes=180), "poza_szkola")
    # weekendy wlaczone do okna
    assert oblicz_interwal({**opcje, CONF_SZKOLA_DNI_ROBOCZE: False}, sobota)[1] == "szkola"
    # niedziela 06:00 -> poniedzialek 07:00 to 25h > 180 min -> 180
    niedziela = datetime(2026, 10, 4, 6, 0)
    assert oblicz_interwal(opcje, niedziela)[0] == timedelta(minutes=180)
    # okno wylaczone (od >= do)
    assert oblicz_interwal({**opcje, CONF_SZKOLA_OD: "15:00:00", CONF_SZKOLA_DO: "07:00:00"}, sroda.replace(hour=9)) == (timedelta(minutes=180), "poza_szkola")
    # minimum 15 min i bledne wartosci
    assert oblicz_interwal({**opcje, CONF_SCAN_INTERVAL_SZKOLA: 1}, sroda.replace(hour=9))[0] == timedelta(minutes=15)
    assert oblicz_interwal({**opcje, CONF_SZKOLA_OD: "zle"}, sroda.replace(hour=9))[1] == "szkola"  # fallback 07:00
    # domyslne (brak opcji)
    assert oblicz_interwal({}, sroda.replace(hour=12)) == (timedelta(minutes=55), "szkola")
    assert oblicz_interwal({}, sroda.replace(hour=20)) == (timedelta(minutes=120), "poza_szkola")


async def test_koordynator_zmienia_interwal(hass: HomeAssistant):
    from custom_components.librus_apix.const import CONF_SCAN_INTERVAL, CONF_SCAN_INTERVAL_SZKOLA
    from homeassistant.util import dt as dt_util
    from datetime import datetime

    options = {CONF_SCAN_INTERVAL: 180, CONF_SCAN_INTERVAL_SZKOLA: 55}
    w_szkole = datetime(2026, 9, 30, 10, 0, tzinfo=dt_util.DEFAULT_TIME_ZONE)
    with patch("custom_components.librus_apix.coordinator.dt_util.now", return_value=w_szkole):
        entry, _ = await _setup(hass, options, [OCENA1], [])
        coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
        assert coordinator.update_interval == timedelta(minutes=55)
        st = hass.states.get("sensor.informacje_o_uczniu")
        assert st.attributes["tryb_sprawdzania"] == "szkola" and st.attributes["interwal_minuty"] == 55

    wieczor = datetime(2026, 9, 30, 20, 0, tzinfo=dt_util.DEFAULT_TIME_ZONE)
    with patch("custom_components.librus_apix.coordinator.dt_util.now", return_value=wieczor):
        await coordinator.async_refresh()
        await hass.async_block_till_done()
        assert coordinator.update_interval == timedelta(minutes=180)
        assert hass.states.get("sensor.informacje_o_uczniu").attributes["tryb_sprawdzania"] == "poza_szkola"
