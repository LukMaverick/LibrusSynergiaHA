"""Budowniczowie danych testowych udajacych obiekty librus_apix."""

import json
from datetime import date, timedelta
from pathlib import Path
from types import SimpleNamespace

FIXTURES = Path(__file__).parent / "fixtures"

GODZINY = {
    0: ("07:00", "07:45"),
    1: ("08:00", "08:45"),
    2: ("08:55", "09:40"),
    3: ("09:50", "10:35"),
    4: ("10:45", "11:30"),
    5: ("11:40", "12:25"),
    6: ("12:35", "13:20"),
}


def fixture(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def period(dzien: date, numer: int, przedmiot: str = "", tc: str = "", info=None):
    od, do = GODZINY[numer]
    return SimpleNamespace(
        subject=przedmiot,
        teacher_and_classroom=tc,
        date=dzien.isoformat(),
        date_from=od,
        date_to=do,
        weekday=dzien.strftime("%A"),
        info=info if info is not None else {},
        number=numer,
        next_recess_from=None,
        next_recess_to=None,
    )


def tydzien(poniedzialek: date, plan: dict):
    """plan: {indeks_dnia: {numer: (przedmiot, tc, info)}} -> lista 7 list Period (jak get_timetable)."""
    wynik = []
    for i in range(7):
        d = poniedzialek + timedelta(days=i)
        lekcje = []
        for numer in range(0, 7):
            wpis = plan.get(i, {}).get(numer)
            if wpis:
                przedmiot, tc, info = (list(wpis) + [None, None])[:3]
                lekcje.append(period(d, numer, przedmiot, tc or "", info))
            else:
                lekcje.append(period(d, numer))
        wynik.append(lekcje)
    return wynik


def homework(**kw):
    return SimpleNamespace(**kw)
