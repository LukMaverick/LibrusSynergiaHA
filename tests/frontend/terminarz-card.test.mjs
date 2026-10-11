import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const here = dirname(fileURLToPath(import.meta.url));
const M = await import(join(here, "../../custom_components/librus_apix/frontend/librus-terminarz-card.js"));
const fiksura = JSON.parse(readFileSync(join(here, "../fixtures/terminarz_typy.json"), "utf8"));

const DZIS = "2026-10-12"; // poniedziałek

const ev = (data, tytul, przedmiot = "Matematyka", extra = {}) => ({
  data, tytul, przedmiot, szczegoly: {}, href: `${data}|${tytul}`, godzina: "unknown", numer_lekcji: "unknown", ...extra,
});

function model(zdarzeniaSurowe, cfg = {}, ui = {}) {
  return {
    cfg: M.normalizujKonfig(cfg),
    zdarzenia: M.normalizujZdarzenia(zdarzeniaSurowe, DZIS),
    dzisIso: DZIS,
    ui: { filtr: "wszystko", rozwiniete: new Set(), pokazWszystko: false, miesiac: { rok: 2026, mies: 9 }, wybranyDzien: null, ...ui },
    blad: null,
    wersjaIntegracji: M.CARD_VERSION,
    granice: { min: 2026 * 12 + 9, max: 2026 * 12 + 10 },
  };
}

test("esc neutralizuje HTML", () => {
  assert.equal(M.esc(`<script>"'&`), "&lt;script&gt;&quot;&#39;&amp;");
  assert.equal(M.esc(null), "");
});

test("klasyfikacja zgodna z fiksurą Pythona", () => {
  for (const p of fiksura) {
    assert.equal(M.klasyfikuj(`${p.tytul} ${p.przedmiot} ${p.opis}`), p.typ, `${p.tytul} / ${p.opis}`);
  }
});

test("etykietaDnia: dziś, jutro, dalej, przełom miesiąca i roku", () => {
  assert.equal(M.etykietaDnia("2026-10-12", DZIS), "Dziś");
  assert.equal(M.etykietaDnia("2026-10-13", DZIS), "Jutro");
  assert.equal(M.etykietaDnia("2026-10-14", DZIS), "Środa, 14 paź");
  assert.equal(M.etykietaDnia("2027-01-01", "2026-12-31"), "Jutro");
  assert.equal(M.roznicaDni("2026-12-30", "2027-01-02"), 3);
});

test("roznicaDni odporna na zmianę czasu", () => {
  assert.equal(M.roznicaDni("2026-10-24", "2026-10-26"), 2); // koniec czasu letniego
  assert.equal(M.roznicaDni("2026-03-28", "2026-03-30"), 2);
});

test("etykietaOdleglosci i odmiana", () => {
  assert.deepEqual([0, 1, 2, 5].map(M.etykietaOdleglosci), ["dziś", "jutro", "pojutrze", "za 5 dni"]);
  const f = M.TYPY.sprawdzian.liczba;
  assert.deepEqual([1, 2, 4, 5, 12, 22].map((n) => M.odmiana(n, f)), ["sprawdzian", "sprawdziany", "sprawdziany", "sprawdzianów", "sprawdzianów", "sprawdziany"]);
});

test("normalizujZdarzenia: filtruje przeszłość, liczy dni_do, fallback typu i szczegółów", () => {
  const z = M.normalizujZdarzenia(
    [
      ev("2026-10-01", "Stary sprawdzian"),
      ev("2026-10-14", "Sprawdzian", "Matematyka", { szczegoly: { Nauczyciel: "Jan Kowalski", Opis: "Ułamki" }, numer_lekcji: 2 }),
      ev("2026-10-13", "Wycieczka klasowa", "unspecified"),
      { data: "zły", tytul: "x" },
      null,
    ],
    DZIS
  );
  assert.equal(z.length, 2);
  assert.equal(z[0].typ, "wycieczka");
  assert.equal(z[0].przedmiot, "");
  assert.equal(z[1].typ, "sprawdzian");
  assert.equal(z[1].dni_do, 2);
  assert.equal(z[1].nauczyciel, "Jan Kowalski");
  assert.equal(z[1].opis, "Ułamki");
  assert.equal(z[1].lekcja, 2);
});

test("normalizujZdarzenie używa pól z integracji gdy są", () => {
  const z = M.normalizujZdarzenie(
    { ...ev("2026-10-14", "Sprawdzian"), typ: "kartkowka", przedmiot_czysty: "Fizyka", lekcja: 3, opis: "Prąd" },
    DZIS
  );
  assert.deepEqual([z.typ, z.przedmiot, z.lekcja, z.opis], ["kartkowka", "Fizyka", 3, "Prąd"]);
  assert.equal(M.normalizujZdarzenie(ev("2026-10-14", "x", "y", { numer_lekcji: "15" }), DZIS).lekcja, null);
});

test("sortowanie: całodniowe pierwsze, lekcja z null na końcu", () => {
  const z = M.normalizujZdarzenia(
    [ev("2026-10-13", "Sprawdzian", "M", { numer_lekcji: 3 }), ev("2026-10-13", "Kartkówka", "P"), ev("2026-10-13", "Rada pedagogiczna", "unspecified"), ev("2026-10-13", "Sprawdzian", "F", { numer_lekcji: 1 })],
    DZIS
  );
  assert.deepEqual(z.map((x) => x.typ), ["rada", "sprawdzian", "sprawdzian", "kartkowka"]);
  assert.equal(z[1].przedmiot, "F");
});

test("filtruj: typy, dni, chip", () => {
  const z = M.normalizujZdarzenia([ev("2026-10-13", "Sprawdzian"), ev("2026-10-14", "Kartkówka"), ev("2026-12-01", "Sprawdzian")], DZIS);
  assert.equal(M.filtruj(z, { typy: ["sprawdzian"] }).length, 2);
  assert.equal(M.filtruj(z, { dni: 30 }).length, 2);
  assert.equal(M.filtruj(z, { filtrId: "kartkowka" }).length, 1);
  assert.equal(M.filtruj(z, { filtrId: "inne" }).length, 0);
});

test("grupowanie po dniach i tygodniach (niedziela -> poniedziałek)", () => {
  const z = M.normalizujZdarzenia(
    [ev("2026-10-12", "Sprawdzian"), ev("2026-10-18", "Kartkówka"), ev("2026-10-19", "Sprawdzian"), ev("2026-10-26", "Test"), ev("2026-10-18", "Test 2")],
    DZIS
  );
  const dni = M.grupujPoDniach(z);
  assert.equal(dni.length, 4);
  const grupy = M.grupujPoTygodniach(dni, DZIS);
  assert.deepEqual(grupy.map((g) => [g.nazwa, g.dni.length]), [["Ten tydzień", 2], ["Następny tydzień", 1], ["Później", 1]]);
});

test("podsumowanie i tekst", () => {
  const z = M.normalizujZdarzenia([ev("2026-10-13", "Sprawdzian"), ev("2026-10-14", "Kartkówka"), ev("2026-10-15", "Sprawdzian", "Fizyka")], DZIS);
  const p = M.podsumuj(z);
  assert.deepEqual([p.sprawdziany, p.kartkowki, p.najblizszy.przedmiot], [2, 1, "Matematyka"]);
  const t = M.tekstPodsumowania(p);
  assert.match(t.html, /<strong>2 sprawdziany<\/strong> i 1 kartkówka w ciągu 7 dni · najbliższy: Matematyka, jutro/);
  assert.equal(t.wazne, true);
  assert.match(M.tekstPodsumowania(M.podsumuj([])).html, /Brak sprawdzianów/);
});

test("siatkaMiesiaca: luty w roku przestępnym i miesiąc zaczynający się w niedzielę", () => {
  const luty = M.siatkaMiesiaca(2028, 1, []);
  assert.equal(luty.flat().filter((k) => k.wMiesiacu).length, 29);
  assert.ok(luty.every((t) => t.length === 7));
  const lutyNiePrzest = M.siatkaMiesiaca(2027, 1, []);
  assert.equal(lutyNiePrzest.length, 4); // 1 lutego 2027 to poniedziałek
  const mar = M.siatkaMiesiaca(2026, 2, []); // 1 marca 2026 = niedziela
  assert.equal(mar[0].findIndex((k) => k.wMiesiacu), 6);
  assert.equal(mar.length, 6);
});

test("normalizujKonfig: domyślne wartości i błędy", () => {
  const c = M.normalizujKonfig({ type: "custom:librus-terminarz-card" });
  assert.deepEqual([c.widok, c.dni, c.filtry, c.pokaz_opis, c.kompakt, c.typy], ["agenda", 30, true, true, false, null]);
  assert.throws(() => M.normalizujKonfig({ widok: "xx" }), /Nieznany widok/);
  assert.throws(() => M.normalizujKonfig({ typy: ["zly"] }), /Nieznane typy/);
  assert.throws(() => M.normalizujKonfig({ dni: 0 }), /dni/);
  assert.throws(() => M.normalizujKonfig(null), /konfiguracji/);
});

test("pola schematu edytora są akceptowane przez normalizujKonfig", () => {
  const przykladowe = { entity: "sensor.a", tytul: "T", widok: "miesiac", dni: 14, typy: ["sprawdzian"], filtry: false, kompakt: true, pokaz_opis: false, pokaz_nauczyciela: true, max_zdarzen: 5 };
  assert.deepEqual(M.EDITOR_SCHEMA.map((s) => s.name).sort(), Object.keys(przykladowe).sort());
  assert.doesNotThrow(() => M.normalizujKonfig(przykladowe));
});

test("znajdzEncjeTerminarza: po platformie i po sygnaturze atrybutów", () => {
  const stan = (extra = {}) => ({ state: "1", attributes: { zdarzenia: [], liczba_zdarzen: 0, ...extra } });
  const hass = {
    states: { "sensor.terminarz": stan(), "sensor.inny": { state: "1", attributes: {} }, "sensor.obcy": stan() },
    entities: { "sensor.terminarz": { platform: "librus_apix" }, "sensor.obcy": { platform: "inna" } },
  };
  assert.deepEqual(M.znajdzEncjeTerminarza(hass), ["sensor.terminarz"]);
  assert.deepEqual(M.znajdzEncjeTerminarza({ states: hass.states }), ["sensor.terminarz", "sensor.obcy"]);
  assert.deepEqual(M.znajdzEncjeTerminarza({}), []);
});

test("render agendy: podświetlenia, grupowanie, XSS", () => {
  const html = M.budujHtml(
    model([
      ev("2026-10-12", "Sprawdzian", "Matematyka", { szczegoly: { Opis: "Ułamki" } }),
      ev("2026-10-14", `<script>alert(1)</script>`, `<img src=x onerror=1>`, { szczegoly: { Opis: `"><svg onload=1>` } }),
      ev("2026-10-15", "Dzień wolny", "unspecified"),
    ])
  );
  assert.match(html, /typ-sprawdzian/);
  assert.match(html, />Dziś</);
  assert.match(html, /Środa, 14 paź/);
  assert.match(html, /dzien ma-sprawdzian/);
  assert.match(html, /dzien wolne/);
  assert.match(html, /Ten tydzień/);
  assert.ok(!/<script>|<img src|<svg/.test(html), "dane muszą być escapowane");
  assert.match(html, /&lt;script&gt;/);
});

test("render: filtry, kompakt, limit, opis rozwinięty, błąd i wersja", () => {
  const dane = [ev("2026-10-13", "Sprawdzian"), ev("2026-10-14", "Kartkówka"), ev("2026-10-15", "Sprawdzian", "Fizyka", { szczegoly: { Opis: "Prąd" } })];
  const h = M.budujHtml(model(dane, {}, { filtr: "kartkowka" }));
  assert.equal((h.match(/class="zd /g) || []).length, 1);
  assert.match(h, /aria-pressed="true"[^>]*>✏️ Kartkówki/);
  assert.ok(!M.budujHtml(model(dane, { filtry: false })).includes("class=\"chipsy\""));
  assert.match(M.budujHtml(model(dane, { kompakt: true })), /zd typ-sprawdzian kompakt/);
  const lim = M.budujHtml(model(dane, { max_zdarzen: 2 }));
  assert.match(lim, /Pokaż więcej \(1\)/);
  assert.ok(!M.budujHtml(model(dane, { max_zdarzen: 2 }, { pokazWszystko: true })).includes("Pokaż więcej"));
  const id = M.normalizujZdarzenia(dane, DZIS)[2].id;
  assert.match(M.budujHtml(model(dane, {}, { rozwiniete: new Set([id]) })), /opis rozwiniety/);
  const m = model(dane);
  assert.match(M.budujHtml({ ...m, blad: "Encja <x> niedostępna" }), /Encja &lt;x&gt; niedostępna/);
  assert.match(M.budujHtml({ ...m, wersjaIntegracji: "0.0.1" }), /różni się od integracji/);
  assert.match(M.budujHtml(model([])), /Brak zdarzeń w najbliższych 30 dniach/);
});

test("render miesiąca: kropki, wybrany dzień, nawigacja", () => {
  const dane = [ev("2026-10-14", "Sprawdzian"), ev("2026-10-14", "Kartkówka", "Fizyka"), ev("2026-10-14", "Wycieczka", "unspecified"), ev("2026-10-14", "Test", "Biologia"), ev("2026-11-02", "Sprawdzian")];
  const h = M.budujHtml(model(dane, { widok: "miesiac" }, { wybranyDzien: "2026-10-14" }));
  assert.match(h, /październik 2026/);
  assert.match(h, /kropka typ-sprawdzian duza/);
  assert.match(h, /\+1/);
  assert.match(h, /aria-label="14 października: Wycieczka, Kartkówka Fizyka, Sprawdzian Matematyka/);
  assert.match(h, /komorka dzis/);
  assert.match(h, /data-kierunek="-1"[^>]*disabled/);
  assert.ok(!/data-kierunek="1"[^>]*disabled/.test(h));
  assert.match(h, /Środa, 14 paź/);
});

test("smoke: element karty renderuje bez wyjątku dla pustych i błędnych danych", () => {
  const karta = new M.LibrusTerminarzCard();
  let html = "";
  Object.defineProperty(karta, "shadowRoot", { value: { set innerHTML(v) { html = v; }, addEventListener() {} } });
  karta.setConfig({ type: "x" });
  assert.match(html, /Wczytywanie/);
  karta.hass = { states: {} };
  assert.match(html, /Nie znaleziono sensora/);
  karta.setConfig({ entity: "sensor.terminarz" });
  karta.hass = { states: { "sensor.terminarz": { state: "unavailable", attributes: {} } } };
  assert.match(html, /niedostępna/);
  karta.hass = { states: { "sensor.terminarz": { state: "1", last_updated: "a", attributes: { zdarzenia: "źle", liczba_zdarzen: 1 } } } };
  assert.match(html, /Brak zdarzeń/);
  assert.throws(() => karta.setConfig({ widok: "zły" }));
  karta.disconnectedCallback();
});
