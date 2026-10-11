// Testy czystych funkcji karty librus-card (node --test tests/frontend/)
import { test, describe } from "node:test";
import assert from "node:assert/strict";

import {
  CARD_VERSION,
  esc,
  normalizuj,
  stylPrzedmiotu,
  skrotPrzedmiotu,
  aktualnaLekcja,
  zbudujSiatke,
  okienka,
  etykietaDnia,
  grupujZadania,
  entityIds,
  wybierzUcznia,
  oknoTygodni,
  przesunTydzien,
  wOknie,
  wyprowadzSlug,
  czyInnaWersja,
  LibrusCard,
} from "../../custom_components/librus_apix/frontend/librus-card.js";

const lekcja = (numer, od, do_, przedmiot = "Matematyka", extra = {}) => ({
  numer,
  od,
  do: do_,
  przedmiot,
  sala: "12",
  zastepstwo: false,
  odwolana: false,
  info: "",
  zmiana: {},
  wydarzenia: [],
  sprawdzian: false,
  zadania: [],
  ...extra,
});

describe("esc", () => {
  test("escapuje znaki specjalne HTML", () => {
    assert.equal(esc(`<script>alert("x")</script>`), "&lt;script&gt;alert(&quot;x&quot;)&lt;/script&gt;");
    assert.equal(esc(`' onerror='a`), "&#39; onerror=&#39;a");
    assert.equal(esc("a & b"), "a &amp; b");
    assert.equal(esc("`x`"), "&#96;x&#96;");
  });
  test("payloady XSS nie zawierają aktywnych znaczników ani wyjścia z atrybutu", () => {
    const payloady = [
      `<img src=x onerror=alert(1)>`,
      `"><svg onload=alert(1)>`,
      `'><iframe src=javascript:alert(1)>`,
      `</style><script>1</script>`,
      `&lt;b&gt;`,
    ];
    for (const p of payloady) {
      const w = esc(p);
      assert.ok(!/[<>"'`]/.test(w), `nieescapowany znak w: ${w}`);
    }
    // podwójne escapowanie encji – pokazujemy dosłownie
    assert.equal(esc("&lt;b&gt;"), "&amp;lt;b&amp;gt;");
  });
  test("null/undefined -> pusty napis, liczby -> tekst", () => {
    assert.equal(esc(null), "");
    assert.equal(esc(undefined), "");
    assert.equal(esc(0), "0");
    assert.equal(esc(false), "false");
  });
});

describe("normalizuj", () => {
  test("usuwa polskie znaki i interpunkcję", () => {
    assert.equal(normalizuj("Język Polski"), "jezyk polski");
    assert.equal(normalizuj("Edukacja dla bezpieczeństwa"), "edukacja dla bezpieczenstwa");
    assert.equal(normalizuj("  Zajęcia z wychowawcą! "), "zajecia z wychowawca");
    assert.equal(normalizuj("ŁÓDŹ żółć"), "lodz zolc");
    assert.equal(normalizuj(null), "");
  });
});

describe("stylPrzedmiotu", () => {
  const przypadki = [
    ["Matematyka", "🔢"],
    ["Język polski", "📖"],
    ["j. polski", "📖"],
    ["Język angielski", "🇬🇧"],
    ["Język niemiecki", "🇩🇪"],
    ["Historia", "🏛️"],
    ["Geografia", "🌍"],
    ["Biologia", "🌿"],
    ["Przyroda", "🌿"],
    ["Chemia", "🧪"],
    ["Fizyka", "⚛️"],
    ["Informatyka", "💻"],
    ["Technika", "🔧"],
    ["Plastyka", "🎨"],
    ["Muzyka", "🎵"],
    ["Wychowanie fizyczne", "⚽"],
    ["WF", "⚽"],
    ["Religia", "✝️"],
    ["Godzina wychowawcza", "👥"],
    ["Zajęcia z wychowawcą", "👥"],
  ];
  for (const [nazwa, emoji] of przypadki) {
    test(`${nazwa} -> ${emoji}`, () => assert.equal(stylPrzedmiotu(nazwa).emoji, emoji));
  }
  test("wychowanie fizyczne nie jest fizyką", () => {
    assert.notEqual(stylPrzedmiotu("Wychowanie fizyczne").emoji, "⚛️");
  });
  test("nieznany przedmiot: 📚 i deterministyczny kolor z hasha", () => {
    const a = stylPrzedmiotu("Zajęcia kreatywne");
    const b = stylPrzedmiotu("zajęcia KREATYWNE");
    assert.equal(a.emoji, "📚");
    assert.equal(a.znany, false);
    assert.equal(a.kolor, b.kolor);
    assert.match(a.kolor, /^\d{1,3} 65% 50%$/);
    assert.match(a.tlo, /^hsl\(.+ \/ 0\.18\)$/);
  });
  test("nadpisania z konfiguracji (także po znormalizowanej nazwie)", () => {
    const nad = { Matematyka: { emoji: "➗", kolor: "120 50% 40%" }, "jezyk polski": { emoji: "✍️" } };
    const s = stylPrzedmiotu("Matematyka", nad);
    assert.equal(s.emoji, "➗");
    assert.equal(s.kolor, "120 50% 40%");
    assert.equal(s.akcent, "hsl(120 50% 40%)");
    assert.equal(stylPrzedmiotu("Język polski", nad).emoji, "✍️");
  });
  test("niebezpieczny kolor z nadpisania jest odrzucany", () => {
    const s = stylPrzedmiotu("Matematyka", { Matematyka: { kolor: 'red;"><script>' } });
    assert.equal(s.kolor, "210 65% 50%");
  });
});

describe("skrotPrzedmiotu", () => {
  test("znane skróty", () => {
    assert.equal(skrotPrzedmiotu("Matematyka"), "Mat.");
    assert.equal(skrotPrzedmiotu("Język polski"), "J. pol.");
    assert.equal(skrotPrzedmiotu("Język angielski"), "J. ang.");
    assert.equal(skrotPrzedmiotu("Wychowanie fizyczne"), "WF");
    assert.equal(skrotPrzedmiotu("Wiedza o społeczeństwie"), "WOS");
  });
  test("krótkie nazwy bez zmian, długie ucięte lub inicjały", () => {
    assert.equal(skrotPrzedmiotu("Chór"), "Chór");
    assert.equal(skrotPrzedmiotu("Robotyka", 8), "Robotyka");
    assert.equal(skrotPrzedmiotu("Programowanie", 8), "Program.");
    assert.equal(skrotPrzedmiotu("Zajęcia rozwijające kreatywność", 8), "ZRK");
    assert.ok(skrotPrzedmiotu("Programowanie", 5).length <= 5);
    assert.equal(skrotPrzedmiotu(""), "");
  });
});

describe("aktualnaLekcja", () => {
  const lekcje = [
    lekcja(1, "08:00", "08:45"),
    lekcja(2, "08:55", "09:40", "Historia"),
    lekcja(3, "09:50", "10:35", "Chemia", { odwolana: true }),
    lekcja(4, "10:45", "11:30", "Biologia"),
  ];
  test("przed lekcjami", () => {
    const w = aktualnaLekcja(lekcje, "07:30");
    assert.equal(w.stan, "przed");
    assert.equal(w.nastepna.numer, 1);
  });
  test("w trakcie lekcji", () => {
    const w = aktualnaLekcja(lekcje, "08:10");
    assert.equal(w.stan, "trwa");
    assert.equal(w.lekcja.numer, 1);
    assert.equal(w.nastepna.numer, 2);
  });
  test("przerwa (pomija odwołaną)", () => {
    const w = aktualnaLekcja(lekcje, "09:45");
    assert.equal(w.stan, "przerwa");
    assert.equal(w.nastepna.numer, 4);
    assert.equal(aktualnaLekcja(lekcje, "10:00").nastepna.numer, 4);
  });
  test("koniec lekcji = 'po'; granica do jest wyłączna", () => {
    assert.equal(aktualnaLekcja(lekcje, "11:30").stan, "po");
    assert.equal(aktualnaLekcja(lekcje, "08:45").stan, "przerwa");
  });
  test("akceptuje obiekt Date", () => {
    const d = new Date(2025, 9, 13, 10, 50);
    assert.equal(aktualnaLekcja(lekcje, d).lekcja.numer, 4);
  });
  test("brak lekcji", () => {
    assert.equal(aktualnaLekcja([], "10:00").stan, "brak");
    assert.equal(aktualnaLekcja(undefined, "10:00").stan, "brak");
  });
});

describe("okienka", () => {
  test("wykrywa luki w numeracji", () => {
    const w = okienka([
      lekcja(1, "08:00", "08:45"),
      lekcja(2, "08:55", "09:40"),
      lekcja(5, "11:40", "12:25"),
      lekcja(7, "13:30", "14:15"),
    ]);
    assert.deepEqual(w, [
      { po: 2, przed: 5, numery: [3, 4], od: "09:40", do: "11:40" },
      { po: 5, przed: 7, numery: [6], od: "12:25", do: "13:30" },
    ]);
  });
  test("lekcje w grupach (ten sam numer) nie tworzą okienek", () => {
    assert.deepEqual(okienka([lekcja(1, "08:00", "08:45"), lekcja(1, "08:00", "08:45", "Fizyka")]), []);
    assert.deepEqual(okienka([]), []);
  });
});

describe("zbudujSiatke", () => {
  const dzien = (data, skrot, lekcje, extra = {}) => ({
    data,
    skrot,
    lekcje,
    liczba_lekcji: lekcje.length,
    dzien_wolny: false,
    wydarzenia_dnia: [],
    ...extra,
  });
  const dni = [
    dzien("2025-10-13", "Pn", [lekcja(1, "08:00", "08:45"), lekcja(3, "09:50", "10:35")]),
    dzien("2025-10-14", "Wt", [lekcja(2, "08:55", "09:40")]),
    dzien("2025-10-15", "Śr", [], { dzien_wolny: true }),
    dzien("2025-10-16", "Cz", [lekcja(1, "08:00", "08:45"), lekcja(1, "08:00", "08:45", "Fizyka")]),
    dzien("2025-10-17", "Pt", [lekcja(0, "07:10", "07:55")]),
    dzien("2025-10-18", "So", []),
    dzien("2025-10-19", "Nd", [lekcja(4, "10:45", "11:30")]),
  ];
  const s = zbudujSiatke(dni, [0, 1, 2, 3]);

  test("kolumny: Pn–Pt zawsze, So pominięta, Nd z lekcjami", () => {
    assert.deepEqual(
      s.kolumny.map((k) => k.skrot),
      ["Pn", "Wt", "Śr", "Cz", "Pt", "Nd"],
    );
    assert.equal(s.kolumny[5].indeks, 6);
  });
  test("wiersze: numery z parametru + z danych (posortowane)", () => {
    assert.deepEqual(
      s.wiersze.map((w) => w.numer),
      [0, 1, 2, 3, 4],
    );
    assert.equal(s.wiersze[1].od, "08:00");
  });
  test("luki i okienka", () => {
    const pn = s.wiersze.map((w) => w.komorki[0]);
    assert.equal(pn[0].luka, true); // lekcja 0 – przed pierwszą, nie okienko
    assert.equal(pn[0].okienko, false);
    assert.equal(pn[1].lekcje.length, 1);
    assert.equal(pn[2].luka, true);
    assert.equal(pn[2].okienko, true); // luka między 1 a 3
    assert.equal(pn[4].okienko, false); // po ostatniej
    const sr = s.wiersze.map((w) => w.komorki[2]);
    assert.ok(sr.every((c) => c.luka && !c.okienko));
  });
  test("kilka lekcji (grupy) w jednej komórce", () => {
    assert.equal(s.wiersze[1].komorki[3].lekcje.length, 2);
  });
  test("puste dane", () => {
    assert.deepEqual(zbudujSiatke(undefined, undefined), { kolumny: [], wiersze: [] });
  });
});

describe("etykietaDnia", () => {
  test("Dzisiaj / Jutro po dacie", () => {
    assert.equal(etykietaDnia({ data: "2025-10-13", dzien: "poniedziałek" }, undefined, "2025-10-13"), "Dzisiaj");
    assert.equal(etykietaDnia({ data: "2025-10-14", dzien: "wtorek" }, undefined, "2025-10-13"), "Jutro");
  });
  test("czy_jutro=true -> Jutro", () => {
    assert.equal(etykietaDnia({ data: "2025-10-14", dzien: "wtorek" }, true, "2025-10-13"), "Jutro");
  });
  test("piątek -> W poniedziałek (czy_jutro=false)", () => {
    assert.equal(etykietaDnia({ data: "2025-10-20", dzien: "poniedziałek" }, false, "2025-10-17"), "W poniedziałek");
  });
  test("odmiana dni w bierniku", () => {
    assert.equal(etykietaDnia("wtorek", false, "2025-10-01"), "We wtorek");
    assert.equal(etykietaDnia("środa", false, "2025-10-01"), "W środę");
    assert.equal(etykietaDnia("sobota", false, "2025-10-01"), "W sobotę");
    assert.equal(etykietaDnia("niedziela", false, "2025-10-01"), "W niedzielę");
  });
  test("brak nazwy dnia – wyliczona z daty", () => {
    assert.equal(etykietaDnia({ data: "2025-10-22" }, false, "2025-10-17"), "W środę");
  });
});

describe("grupujZadania", () => {
  const z = (id, pilnosc, termin, przedmiot = "Matematyka", dni_do = null) => ({
    id,
    przedmiot,
    kategoria: "Zadanie",
    termin,
    dni_do,
    pilnosc,
    tresc: null,
  });
  test("grupy wg pilnosc, brak_terminu -> pozniej, sortowanie po terminie", () => {
    const g = grupujZadania([
      z(1, "tydzien", "2025-10-17"),
      z(2, "dzis", "2025-10-13"),
      z(3, "tydzien", "2025-10-15"),
      z(4, "brak_terminu", null),
      z(5, "pozniej", "2025-11-01"),
      z(6, "po_terminie", "2025-10-10"),
      z(7, "jutro", "2025-10-14"),
    ]);
    assert.deepEqual(g.dzis.map((x) => x.id), [2]);
    assert.deepEqual(g.jutro.map((x) => x.id), [7]);
    assert.deepEqual(g.tydzien.map((x) => x.id), [3, 1]);
    assert.deepEqual(g.pozniej.map((x) => x.id), [5, 4]);
    assert.deepEqual(g.po_terminie.map((x) => x.id), [6]);
  });
  test("deduplikacja po id (zadania + po_terminie)", () => {
    const a = z(9, "po_terminie", "2025-10-01");
    const g = grupujZadania([a, { ...a }]);
    assert.equal(g.po_terminie.length, 1);
  });
  test("nieznana pilnosc -> z dni_do", () => {
    const g = grupujZadania([z(1, undefined, "2025-10-12", "X", -1), z(2, "?", "2025-10-14", "X", 1)]);
    assert.equal(g.po_terminie.length, 1);
    assert.equal(g.jutro.length, 1);
  });
  test("pusto", () => {
    const g = grupujZadania(null);
    assert.deepEqual(Object.keys(g), ["dzis", "jutro", "tydzien", "pozniej", "po_terminie"]);
    assert.ok(Object.values(g).every((l) => l.length === 0));
  });
});

describe("entityIds / wyprowadzSlug", () => {
  test("encje ucznia", () => {
    assert.deepEqual(entityIds("Ola"), {
      plan_dzis: "sensor.librus_ola_plan_dzis",
      plan_jutro: "sensor.librus_ola_plan_jutro",
      nastepna_lekcja: "sensor.librus_ola_nastepna_lekcja",
      plan_tygodnia: "sensor.librus_ola_plan_tygodnia",
      do_zrobienia_jutro: "sensor.librus_ola_do_zrobienia_jutro",
      zadania_otwarte: "sensor.librus_ola_zadania_otwarte",
    });
  });
  test("getStubConfig/wyprowadzSlug szuka plan_tygodnia", () => {
    const states = {
      "sensor.librus_jan_kowalski_plan_dzis": {},
      "sensor.librus_jan_kowalski_plan_tygodnia": {},
    };
    assert.equal(wyprowadzSlug(states), "jan_kowalski");
    assert.equal(wyprowadzSlug({}), null);
    assert.equal(LibrusCard.getStubConfig({ states }).slug, "jan_kowalski");
    assert.equal(LibrusCard.getStubConfig({ states }).type, "custom:librus-card");
  });
});

describe("wybierzUcznia", () => {
  const config = { uczniowie: [{ slug: "ola", numer_w_dzienniku: 7 }, { slug: "tomek", nazwa: "Tomuś" }] };
  test("bez zapisu -> pierwszy, nazwa domyślna z wielkiej litery", () => {
    const { uczniowie, wybrany } = wybierzUcznia(config, null);
    assert.equal(uczniowie.length, 2);
    assert.equal(wybrany.slug, "ola");
    assert.equal(wybrany.nazwa, "Ola");
    assert.equal(wybrany.numer_w_dzienniku, 7);
    assert.equal(uczniowie[1].nazwa, "Tomuś");
  });
  test("z zapisem -> zapisany", () => {
    assert.equal(wybierzUcznia(config, "tomek").wybrany.slug, "tomek");
  });
  test("zapisany nieistniejący -> pierwszy", () => {
    assert.equal(wybierzUcznia(config, "kasia").wybrany.slug, "ola");
  });
  test("skrót slug", () => {
    const w = wybierzUcznia({ slug: "Ola" }, "tomek");
    assert.equal(w.uczniowie.length, 1);
    assert.equal(w.wybrany.slug, "ola");
  });
  test("brak ucznia", () => {
    assert.equal(wybierzUcznia({}, null).wybrany, null);
    assert.equal(wybierzUcznia(null, null).wybrany, null);
  });
});

describe("tygodnie", () => {
  test("przesunTydzien", () => {
    assert.equal(przesunTydzien("2025-10-13", 1), "2025-10-20");
    assert.equal(przesunTydzien("2025-10-13", -2), "2025-09-29");
    assert.equal(przesunTydzien("2025-12-29", 1), "2026-01-05");
    assert.equal(przesunTydzien("2025-10-16", 0), "2025-10-13"); // normalizacja do poniedziałku
    assert.equal(przesunTydzien("2026-03-23", 1), "2026-03-30"); // przez zmianę czasu
  });
  test("oknoTygodni -2…+4", () => {
    const o = oknoTygodni("2025-10-15");
    assert.deepEqual(o, { biezacy: "2025-10-13", od: "2025-09-29", do: "2025-11-10" });
    assert.ok(wOknie("2025-09-29", o));
    assert.ok(!wOknie("2025-09-22", o));
    assert.ok(wOknie("2025-11-10", o));
    assert.ok(!wOknie("2025-11-17", o));
  });
  test("niedziela należy do tygodnia od poprzedniego poniedziałku", () => {
    assert.equal(oknoTygodni("2025-10-19").biezacy, "2025-10-13");
  });
});

describe("wersja", () => {
  test("CARD_VERSION i porównanie", () => {
    assert.equal(CARD_VERSION, "1.3.0");
    assert.equal(czyInnaWersja("1.3.0", "1.3.0"), false);
    assert.equal(czyInnaWersja("1.3.0", "1.3.1"), true);
    assert.equal(czyInnaWersja("1.3.0", undefined), false);
  });
});

describe("render (bez DOM) – dane są escapowane we wszystkich widokach", () => {
  const XSS = `<img src=x onerror=alert(1)>`;
  const zly = lekcja(1, "08:00", "08:45", XSS, {
    nauczyciel: XSS,
    sala: XSS,
    info: XSS,
    zastepstwo: true,
    zmiana: { teacher_swap: XSS },
    sprawdzian: true,
    wydarzenia: [{ typ: "sprawdzian", ikona: XSS, tytul: XSS, przedmiot: XSS }],
    zadania: [{ id: XSS, kategoria: XSS, tresc: XSS, przedmiot: XSS }],
  });
  const dzien = {
    data: "2025-10-13",
    dzien: XSS,
    skrot: XSS,
    liczba_lekcji: 1,
    zakres: XSS,
    dzien_wolny: false,
    wydarzenia_dnia: [{ typ: XSS, ikona: XSS, tytul: XSS, przedmiot: XSS }],
    lekcje: [zly, lekcja(3, "09:50", "10:35")],
  };
  const zad = { id: 1, przedmiot: XSS, kategoria: XSS, tresc: XSS, termin: "2025-10-14", termin_raw: XSS, dni_do: 1, pilnosc: "jutro" };
  const hass = {
    states: {
      "sensor.librus_ola_plan_dzis": { state: XSS, attributes: { ...dzien } },
      "sensor.librus_ola_plan_jutro": { state: XSS, attributes: { ...dzien, czy_jutro: false } },
      "sensor.librus_ola_plan_tygodnia": {
        state: XSS,
        attributes: { tydzien_od: "2025-10-13", numery_lekcji: [1, 2, 3], godziny: { 1: XSS }, dni: [dzien], wersja_integracji: XSS },
      },
      "sensor.librus_ola_zadania_otwarte": { state: "1", attributes: { zadania: [zad], po_terminie: [{ ...zad, id: 2, pilnosc: "po_terminie" }] } },
      "sensor.librus_ola_do_zrobienia_jutro": {
        state: "1",
        attributes: { data: "2025-10-14", dzien: XSS, zadania: [zad], sprawdziany: [{ typ: XSS, ikona: XSS, tytul: XSS, przedmiot: XSS }], przedmioty_do_spakowania: [XSS] },
      },
      "sensor.numerek": { state: XSS },
    },
  };
  for (const widok of ["dzis", "jutro", "tydzien", "zadania", "plecak"]) {
    test(widok, () => {
      const karta = new LibrusCard();
      karta._config = {
        widok,
        uczniowie: [{ slug: "ola", nazwa: XSS, numerek: "sensor.numerek" }, { slug: "tomek" }],
        przedmioty: { [XSS]: { emoji: XSS } },
      };
      karta._hass = hass;
      karta._teraz = () => new Date(2025, 9, 13, 8, 10);
      const html = karta._html();
      assert.ok(html.length > 200);
      assert.ok(!html.includes("<img"), `surowy znacznik w widoku ${widok}`);
      assert.ok(html.includes("&lt;img src=x onerror=alert(1)&gt;"));
    });
  }
  test("brakująca encja -> komunikat, nie wyjątek", () => {
    const karta = new LibrusCard();
    karta._config = { widok: "tydzien", slug: "nikt" };
    karta._hass = { states: {} };
    assert.match(karta._html(), /Nie znaleziono encji/);
  });
  test("setConfig waliduje widok", () => {
    const karta = new LibrusCard();
    assert.throws(() => karta.setConfig({ widok: "xyz", slug: "ola" }), /Nieznany widok/);
    assert.throws(() => karta.setConfig({ widok: "dzis" }), /slug/);
  });
});
