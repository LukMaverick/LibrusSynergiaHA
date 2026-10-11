/*
 * librus-terminarz-card - karta Lovelace z terminarzem Librus Synergia.
 * Samowystarczalny moduł (bez importów), czyta atrybuty sensora Terminarz z integracji librus_apix.
 * Każda wartość z danych trafia do HTML wyłącznie przez esc().
 */

export const CARD_VERSION = "1.2.0";

const DNI = ["poniedziałek", "wtorek", "środa", "czwartek", "piątek", "sobota", "niedziela"];
const SKROTY_DNI = ["Pn", "Wt", "Śr", "Cz", "Pt", "So", "Nd"];
const MIESIACE_SKROT = ["sty", "lut", "mar", "kwi", "maj", "cze", "lip", "sie", "wrz", "paź", "lis", "gru"];
const MIESIACE = [
  "styczeń", "luty", "marzec", "kwiecień", "maj", "czerwiec",
  "lipiec", "sierpień", "wrzesień", "październik", "listopad", "grudzień",
];
const MIESIACE_DOP = [
  "stycznia", "lutego", "marca", "kwietnia", "maja", "czerwca",
  "lipca", "sierpnia", "września", "października", "listopada", "grudnia",
];

export const WIDOKI = ["agenda", "miesiac"];

// Metadane typów: ikona, etykieta odznaki (nigdy sam kolor nie niesie informacji)
export const TYPY = {
  sprawdzian: { ikona: "📝", etykieta: "Sprawdzian", liczba: ["sprawdzian", "sprawdziany", "sprawdzianów"] },
  kartkowka: { ikona: "✏️", etykieta: "Kartkówka", liczba: ["kartkówka", "kartkówki", "kartkówek"] },
  dzien_wolny: { ikona: "🎉", etykieta: "Wolne" },
  wycieczka: { ikona: "🚌", etykieta: "Wycieczka" },
  odwolane: { ikona: "❌", etykieta: "Odwołane" },
  rada: { ikona: "👥", etykieta: "Rada" },
  zebranie: { ikona: "👥", etykieta: "Zebranie" },
  inne: { ikona: "📌", etykieta: "" },
};
export const WSZYSTKIE_TYPY = Object.keys(TYPY);

// Chipsy filtrów (grupy typów)
export const FILTRY = [
  { id: "wszystko", etykieta: "Wszystko", typy: null },
  { id: "sprawdzian", etykieta: "📝 Sprawdziany", typy: ["sprawdzian"] },
  { id: "kartkowka", etykieta: "✏️ Kartkówki", typy: ["kartkowka"] },
  { id: "wolne", etykieta: "🎉 Wolne", typy: ["dzien_wolny"] },
  { id: "wycieczka", etykieta: "🚌 Wycieczki", typy: ["wycieczka"] },
  { id: "inne", etykieta: "Inne", typy: ["odwolane", "rada", "zebranie", "inne"] },
];

// Reguły klasyfikacji używane tylko gdy integracja nie podała pola `typ` (1:1 z const.REGULY_TYPOW)
export const REGULY_TYPOW = [
  ["odwolane", ["odwolan"]],
  ["dzien_wolny", ["dzien wolny", "dni wolne", "wolne od zajec", "ferie", "przerwa swiateczna", "dyrektorski", "dzien dyrektorski"]],
  ["kartkowka", ["kartkowk"]],
  ["sprawdzian", ["sprawdzian", "klasowk", "praca klasowa", "pisemn", "test"]],
  ["wycieczka", ["wycieczk", "wyjscie", "wyjazd"]],
  ["rada", ["rada pedagogiczna"]],
  ["zebranie", ["zebranie", "wywiadowk"]],
];

// ---------- czyste funkcje (testowane w Node) ----------

export function esc(v) {
  return String(v ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

export function normalizuj(s) {
  return String(s ?? "")
    .toLowerCase()
    .replace(/ł/g, "l")
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .replace(/[^a-z0-9]+/g, " ")
    .trim();
}

const pad = (n) => String(n).padStart(2, "0");

/** "YYYY-MM-DD" -> lokalna data (bez przesunięcia UTC) albo null. */
export function parsujIso(iso) {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(String(iso ?? ""));
  if (!m) return null;
  const d = new Date(Number(m[1]), Number(m[2]) - 1, Number(m[3]));
  return d.getMonth() === Number(m[2]) - 1 ? d : null;
}

export function dataIso(d) {
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

export function dodajDni(iso, n) {
  const d = parsujIso(iso);
  d.setDate(d.getDate() + n);
  return dataIso(d);
}

/** Różnica w pełnych dniach kalendarzowych (odporna na zmianę czasu). */
export function roznicaDni(odIso, doIso) {
  const a = parsujIso(odIso);
  const b = parsujIso(doIso);
  return Math.round((Date.UTC(b.getFullYear(), b.getMonth(), b.getDate()) - Date.UTC(a.getFullYear(), a.getMonth(), a.getDate())) / 86400000);
}

export function poniedzialek(iso) {
  const d = parsujIso(iso);
  return dodajDni(iso, -((d.getDay() + 6) % 7));
}

export function dzienTygodniaNr(iso) {
  return (parsujIso(iso).getDay() + 6) % 7;
}

export function krotkaData(iso) {
  const d = parsujIso(iso);
  return `${d.getDate()} ${MIESIACE_SKROT[d.getMonth()]}`;
}

export function etykietaDnia(iso, dzisIso) {
  const n = roznicaDni(dzisIso, iso);
  if (n === 0) return "Dziś";
  if (n === 1) return "Jutro";
  const nazwa = DNI[dzienTygodniaNr(iso)];
  return `${nazwa[0].toUpperCase()}${nazwa.slice(1)}, ${krotkaData(iso)}`;
}

export function etykietaOdleglosci(n) {
  if (n === 0) return "dziś";
  if (n === 1) return "jutro";
  if (n === 2) return "pojutrze";
  if (n < 0) return `${-n} dni temu`;
  return `za ${n} dni`;
}

export function odmiana(n, formy) {
  if (n === 1) return formy[0];
  const r10 = n % 10;
  const r100 = n % 100;
  return r10 >= 2 && r10 <= 4 && !(r100 >= 12 && r100 <= 14) ? formy[1] : formy[2];
}

function slowoKlucz(tekst, klucz) {
  return new RegExp("(^| )" + normalizuj(klucz).replace(/[.*+?^${}()|[\]\\]/g, "\\$&")).test(tekst);
}

/** Fallback klasyfikacji (gdy dane nie mają `typ`); parzystość z Pythonem pilnuje wspólna fiksura. */
export function klasyfikuj(tekst) {
  const norm = normalizuj(tekst);
  for (const [typ, slowa] of REGULY_TYPOW) {
    if (slowa.some((s) => slowoKlucz(norm, s))) return typ;
  }
  return "inne";
}

function czysty(v) {
  const t = String(v ?? "").replace(/<[^>]+>/g, " ").replace(/\s+/g, " ").trim();
  return ["", "unknown", "unspecified"].includes(normalizuj(t)) ? "" : t;
}

/**
 * Ujednolica zdarzenie z atrybutu sensora; brakujące pola (starsza integracja) liczy lokalnie.
 * `dni_do` zawsze liczone względem lokalnej daty przeglądarki.
 */
export function normalizujZdarzenie(ev, dzisIso) {
  const sz = ev && typeof ev.szczegoly === "object" && ev.szczegoly ? ev.szczegoly : {};
  const klucz = (nazwa) => {
    const k = Object.keys(sz).find((x) => normalizuj(x) === nazwa);
    return k ? czysty(sz[k]) : "";
  };
  const opis = czysty(ev.opis) || klucz("opis");
  const nauczyciel = czysty(ev.nauczyciel) || klucz("nauczyciel");
  const tytul = String(ev.tytul ?? "");
  let typ = ev.typ;
  if (!TYPY[typ]) typ = klasyfikuj(`${tytul} ${ev.przedmiot ?? ""} ${opis}`);
  let przedmiot = ev.przedmiot_czysty !== undefined ? czysty(ev.przedmiot_czysty) : czysty(ev.przedmiot);
  if (normalizuj(przedmiot) === normalizuj(tytul)) przedmiot = "";
  const lekcjaSurowa = ev.lekcja !== undefined ? ev.lekcja : ev.numer_lekcji;
  const lekcjaNr = Number.parseInt(lekcjaSurowa, 10);
  const godzina = czysty(ev.godzina);
  return {
    id: String(ev.id ?? ev.href ?? `${ev.data}|${tytul}|${ev.przedmiot ?? ""}`),
    data: String(ev.data ?? ""),
    typ,
    tytul,
    przedmiot,
    opis,
    nauczyciel,
    lekcja: Number.isInteger(lekcjaNr) && lekcjaNr >= 0 && lekcjaNr <= 12 ? lekcjaNr : null,
    godzina,
    dni_do: roznicaDni(dzisIso, ev.data),
  };
}

export function normalizujZdarzenia(lista, dzisIso) {
  const wynik = [];
  for (const ev of Array.isArray(lista) ? lista : []) {
    if (!ev || !parsujIso(ev.data)) continue;
    const z = normalizujZdarzenie(ev, dzisIso);
    if (z.dni_do >= 0) wynik.push(z);
  }
  const calodniowe = new Set(["dzien_wolny", "wycieczka", "rada", "zebranie"]);
  wynik.sort(
    (a, b) =>
      a.data.localeCompare(b.data) ||
      (calodniowe.has(b.typ) ? 1 : 0) - (calodniowe.has(a.typ) ? 1 : 0) ||
      (a.lekcja ?? 99) - (b.lekcja ?? 99) ||
      a.godzina.localeCompare(b.godzina) ||
      a.tytul.localeCompare(b.tytul)
  );
  return wynik;
}

export function normalizujKonfig(config) {
  if (!config || typeof config !== "object") throw new Error("Brak konfiguracji karty");
  const widok = config.widok ?? "agenda";
  if (!WIDOKI.includes(widok)) throw new Error(`Nieznany widok „${widok}”. Dostępne: ${WIDOKI.join(", ")}`);
  const typy = config.typy ?? null;
  if (typy !== null) {
    if (!Array.isArray(typy)) throw new Error("Pole „typy” musi być listą");
    const zle = typy.filter((t) => !WSZYSTKIE_TYPY.includes(t));
    if (zle.length) throw new Error(`Nieznane typy: ${zle.join(", ")}. Dostępne: ${WSZYSTKIE_TYPY.join(", ")}`);
  }
  const dni = config.dni === undefined ? 30 : Number(config.dni);
  if (!Number.isInteger(dni) || dni < 1 || dni > 365) throw new Error("Pole „dni” musi być liczbą od 1 do 365");
  const maks = config.max_zdarzen === undefined ? 0 : Number(config.max_zdarzen);
  if (!Number.isInteger(maks) || maks < 0) throw new Error("Pole „max_zdarzen” musi być liczbą całkowitą >= 0");
  return {
    entity: config.entity ? String(config.entity) : null,
    tytul: config.tytul === undefined ? "Terminarz" : String(config.tytul),
    widok,
    dni,
    typy: typy && typy.length ? typy : null,
    filtry: config.filtry !== false,
    kompakt: config.kompakt === true,
    pokaz_opis: config.pokaz_opis !== false,
    pokaz_nauczyciela: config.pokaz_nauczyciela === true,
    max_zdarzen: maks,
  };
}

/** Zdarzenia po filtrach konfiguracji (typy, horyzont) i opcjonalnym chipsie. */
export function filtruj(zdarzenia, opcje = {}) {
  const { typy = null, dni = null, filtrId = "wszystko" } = opcje;
  const chip = FILTRY.find((f) => f.id === filtrId) ?? FILTRY[0];
  return zdarzenia.filter(
    (z) =>
      (!typy || typy.includes(z.typ)) &&
      (dni === null || z.dni_do < dni) &&
      (!chip.typy || chip.typy.includes(z.typ))
  );
}

export function grupujPoDniach(zdarzenia) {
  const mapa = new Map();
  for (const z of zdarzenia) {
    if (!mapa.has(z.data)) mapa.set(z.data, []);
    mapa.get(z.data).push(z);
  }
  return [...mapa.entries()].map(([data, lista]) => ({ data, zdarzenia: lista }));
}

/** Grupy: Ten tydzień / Następny tydzień / Później (tygodnie od poniedziałku). */
export function grupujPoTygodniach(dni, dzisIso) {
  const pn = poniedzialek(dzisIso);
  const wynik = [];
  for (const d of dni) {
    const tydz = Math.floor(roznicaDni(pn, d.data) / 7);
    const nazwa = tydz <= 0 ? "Ten tydzień" : tydz === 1 ? "Następny tydzień" : "Później";
    let g = wynik[wynik.length - 1];
    if (!g || g.nazwa !== nazwa) {
      g = { nazwa, dni: [] };
      wynik.push(g);
    }
    g.dni.push(d);
  }
  return wynik;
}

export function liczniki(zdarzenia) {
  const mapa = {};
  for (const f of FILTRY) {
    mapa[f.id] = f.typy ? zdarzenia.filter((z) => f.typy.includes(z.typ)).length : zdarzenia.length;
  }
  return mapa;
}

/** Podsumowanie: sprawdziany/kartkówki w 7 dni + najbliższy sprawdzian. */
export function podsumuj(zdarzenia) {
  const okno = zdarzenia.filter((z) => z.dni_do <= 6);
  const sprawdziany = okno.filter((z) => z.typ === "sprawdzian").length;
  const kartkowki = okno.filter((z) => z.typ === "kartkowka").length;
  const najblizszy = zdarzenia.find((z) => z.typ === "sprawdzian" || z.typ === "kartkowka") ?? null;
  return { sprawdziany, kartkowki, najblizszy };
}

export function tekstPodsumowania(p) {
  if (!p.sprawdziany && !p.kartkowki) {
    return { html: "Brak sprawdzianów w ciągu 7 dni 🎉", wazne: false };
  }
  const czesci = [];
  if (p.sprawdziany) czesci.push(`<strong>${p.sprawdziany} ${odmiana(p.sprawdziany, TYPY.sprawdzian.liczba)}</strong>`);
  if (p.kartkowki) czesci.push(`${p.kartkowki} ${odmiana(p.kartkowki, TYPY.kartkowka.liczba)}`);
  let html = `${czesci.join(" i ")} w ciągu 7 dni`;
  if (p.najblizszy) {
    html += ` · najbliższy: ${esc(p.najblizszy.przedmiot || p.najblizszy.tytul)}, ${etykietaOdleglosci(p.najblizszy.dni_do)}`;
  }
  return { html, wazne: p.sprawdziany > 0 };
}

/** Siatka miesiąca (tygodnie od poniedziałku); mies0 = 0..11. */
export function siatkaMiesiaca(rok, mies0, zdarzenia) {
  const pierwszy = dataIso(new Date(rok, mies0, 1));
  const start = poniedzialek(pierwszy);
  const ostatni = dataIso(new Date(rok, mies0 + 1, 0));
  const poDniach = new Map();
  for (const z of zdarzenia) {
    if (!poDniach.has(z.data)) poDniach.set(z.data, []);
    poDniach.get(z.data).push(z);
  }
  const tygodnie = [];
  let cur = start;
  while (cur <= ostatni) {
    const tydzien = [];
    for (let i = 0; i < 7; i++) {
      const d = parsujIso(cur);
      tydzien.push({
        iso: cur,
        dzien: d.getDate(),
        wMiesiacu: d.getMonth() === mies0,
        zdarzenia: poDniach.get(cur) ?? [],
      });
      cur = dodajDni(cur, 1);
    }
    tygodnie.push(tydzien);
  }
  return tygodnie;
}

/** Encje terminarza: po platformie librus_apix, a w razie braku po sygnaturze atrybutów. */
export function znajdzEncjeTerminarza(hass) {
  const stany = hass?.states ?? {};
  const wynik = [];
  for (const [id, st] of Object.entries(stany)) {
    if (!id.startsWith("sensor.")) continue;
    const a = st?.attributes ?? {};
    if (!Array.isArray(a.zdarzenia) || !("liczba_zdarzen" in a)) continue;
    wynik.push(id);
  }
  const platformy = hass?.entities;
  if (platformy) {
    const librus = wynik.filter((id) => platformy[id]?.platform === "librus_apix");
    if (librus.length) return librus;
  }
  return wynik;
}

export function czyInnaWersja(wersjaIntegracji) {
  return Boolean(wersjaIntegracji) && String(wersjaIntegracji) !== CARD_VERSION;
}

// ---------- renderowanie (czysty HTML z modelu) ----------

function wierszZdarzenia(z, cfg, ui) {
  const meta = TYPY[z.typ];
  const czesci = [];
  if (z.lekcja !== null) czesci.push(`lekcja ${z.lekcja}`);
  else if (z.godzina) czesci.push(esc(z.godzina));
  const nt = normalizuj(z.tytul);
  if (z.przedmiot && nt && nt !== normalizuj(meta.etykieta) && nt !== "sprawdzian" && nt !== "kartkowka") {
    czesci.push(esc(z.tytul));
  }
  if (cfg.pokaz_nauczyciela && z.nauczyciel) czesci.push(esc(z.nauczyciel));
  const glowna = z.przedmiot || z.tytul;
  const odznaka = meta.etykieta ? `<span class="odznaka">${esc(meta.etykieta)}</span>` : "";
  const rozwiniety = ui.rozwiniete.has(z.id);
  const opis =
    cfg.pokaz_opis && !cfg.kompakt && z.opis
      ? `<button type="button" class="opis${rozwiniety ? " rozwiniety" : ""}" data-akcja="opis" data-id="${esc(z.id)}" aria-expanded="${rozwiniety}">${esc(z.opis)}</button>`
      : "";
  if (cfg.kompakt) {
    return `<li class="zd typ-${z.typ} kompakt"><span class="ikona" aria-hidden="true">${meta.ikona}</span><span class="glowna">${esc(glowna)}</span>${odznaka}${
      czesci.length ? `<span class="meta">${czesci.join(" · ")}</span>` : ""
    }</li>`;
  }
  return `<li class="zd typ-${z.typ}">
    <span class="ikona" aria-hidden="true">${meta.ikona}</span>
    <div class="tresc">
      <div class="linia"><span class="glowna">${esc(glowna)}</span>${odznaka}</div>
      ${czesci.length ? `<div class="meta">${czesci.join(" · ")}</div>` : ""}
      ${opis}
    </div>
  </li>`;
}

function sekcjaDnia(d, dzisIso, cfg, ui) {
  const n = roznicaDni(dzisIso, d.data);
  const maSprawdzian = d.zdarzenia.some((z) => z.typ === "sprawdzian");
  const wolne = d.zdarzenia.some((z) => z.typ === "dzien_wolny");
  const klasa = maSprawdzian ? " ma-sprawdzian" : wolne ? " wolne" : "";
  return `<section class="dzien${klasa}">
    <h3 class="dzien-naglowek"><span class="nazwa">${esc(etykietaDnia(d.data, dzisIso))}</span>${
      n <= 1 ? `<span class="data">${esc(krotkaData(d.data))}</span>` : ""
    }<span class="odl">${esc(etykietaOdleglosci(n))}</span></h3>
    <ul class="lista">${d.zdarzenia.map((z) => wierszZdarzenia(z, cfg, ui)).join("")}</ul>
  </section>`;
}

function widokAgendy(zdarzenia, dzisIso, cfg, ui) {
  if (!zdarzenia.length) {
    return `<div class="pusto">Brak zdarzeń w najbliższych ${cfg.dni} dniach</div>`;
  }
  let lista = zdarzenia;
  let ukryte = 0;
  if (cfg.max_zdarzen > 0 && !ui.pokazWszystko && zdarzenia.length > cfg.max_zdarzen) {
    lista = zdarzenia.slice(0, cfg.max_zdarzen);
    ukryte = zdarzenia.length - lista.length;
  }
  const grupy = grupujPoTygodniach(grupujPoDniach(lista), dzisIso);
  const html = grupy
    .map((g) => `<div class="tydzien"><h4 class="tydzien-naglowek">${esc(g.nazwa)}</h4>${g.dni.map((d) => sekcjaDnia(d, dzisIso, cfg, ui)).join("")}</div>`)
    .join("");
  const wiecej = ukryte
    ? `<button type="button" class="wiecej" data-akcja="wiecej">Pokaż więcej (${ukryte})</button>`
    : "";
  return html + wiecej;
}

function widokMiesiaca(zdarzenia, dzisIso, cfg, ui, granice) {
  const { rok, mies } = ui.miesiac;
  const tygodnie = siatkaMiesiaca(rok, mies, zdarzenia);
  const poprz = rok * 12 + mies > granice.min;
  const nast = rok * 12 + mies < granice.max;
  const naglowek = `<div class="mies-nawigacja">
    <button type="button" class="strzalka" data-akcja="mies" data-kierunek="-1" aria-label="Poprzedni miesiąc"${poprz ? "" : " disabled"}>‹</button>
    <span class="mies-tytul">${esc(MIESIACE[mies])} ${rok}</span>
    <button type="button" class="strzalka" data-akcja="mies" data-kierunek="1" aria-label="Następny miesiąc"${nast ? "" : " disabled"}>›</button>
  </div>`;
  const dniNaglowek = SKROTY_DNI.map((s) => `<span class="dn">${s}</span>`).join("");
  const komorki = tygodnie
    .flat()
    .map((k) => {
      const przeszly = k.iso < dzisIso;
      const typy = k.zdarzenia.map((z) => z.typ);
      const kropki = k.zdarzenia
        .slice(0, 3)
        .map((z) => `<i class="kropka typ-${z.typ}${z.typ === "sprawdzian" ? " duza" : ""}"></i>`)
        .join("");
      const wiecej = k.zdarzenia.length > 3 ? `<span class="plus">+${k.zdarzenia.length - 3}</span>` : "";
      const d = parsujIso(k.iso);
      const opisy = k.zdarzenia.map((z) => `${TYPY[z.typ].etykieta || "Zdarzenie"}${z.przedmiot ? ` ${z.przedmiot}` : ""}`).join(", ");
      const aria = `${d.getDate()} ${MIESIACE_DOP[d.getMonth()]}${opisy ? `: ${opisy}` : ": brak zdarzeń"}`;
      const klasy = ["komorka"];
      if (!k.wMiesiacu) klasy.push("obcy");
      if (przeszly) klasy.push("przeszly");
      if (k.iso === dzisIso) klasy.push("dzis");
      if (k.iso === ui.wybranyDzien) klasy.push("wybrany");
      if (typy.includes("sprawdzian")) klasy.push("ma-sprawdzian");
      return `<button type="button" class="${klasy.join(" ")}" data-akcja="dzien" data-data="${esc(k.iso)}" aria-label="${esc(aria)}" aria-pressed="${k.iso === ui.wybranyDzien}"><span class="num">${k.dzien}</span><span class="kropki">${kropki}${wiecej}</span></button>`;
    })
    .join("");
  const wybrane = ui.wybranyDzien ? zdarzenia.filter((z) => z.data === ui.wybranyDzien) : [];
  let szczegoly = "";
  if (ui.wybranyDzien) {
    szczegoly = wybrane.length
      ? sekcjaDnia({ data: ui.wybranyDzien, zdarzenia: wybrane }, dzisIso, cfg, ui)
      : `<div class="pusto">Brak zdarzeń ${esc(krotkaData(ui.wybranyDzien))}</div>`;
  }
  return `${naglowek}<div class="siatka" role="group" aria-label="${esc(MIESIACE[mies])} ${rok}">${dniNaglowek}${komorki}</div><div class="wybrany-dzien">${szczegoly}</div>`;
}

/** Cały HTML karty z modelu (czysta funkcja - łatwa do testowania). */
export function budujHtml(model) {
  const { cfg, zdarzenia, dzisIso, ui, blad, wersjaIntegracji, granice } = model;
  const tytul = cfg.tytul ? `<h2 class="tytul">${esc(cfg.tytul)}</h2>` : "";
  if (blad) {
    return `<ha-card>${tytul}<div class="pusto" role="alert">${esc(blad)}</div></ha-card>`;
  }
  const bazowe = filtruj(zdarzenia, { typy: cfg.typy, dni: cfg.widok === "agenda" ? cfg.dni : null });
  const widoczne = filtruj(bazowe, { filtrId: ui.filtr });
  const pod = tekstPodsumowania(podsumuj(filtruj(zdarzenia, { typy: cfg.typy })));
  const wersja = czyInnaWersja(wersjaIntegracji)
    ? `<div class="wersja" role="status">Wersja karty (${esc(CARD_VERSION)}) różni się od integracji (${esc(wersjaIntegracji)}). Odśwież stronę (Ctrl+Shift+R).</div>`
    : "";
  let chipsy = "";
  if (cfg.filtry) {
    const l = liczniki(bazowe);
    chipsy = `<div class="chipsy" role="group" aria-label="Filtr typu zdarzeń">${FILTRY.filter((f) => f.id === "wszystko" || l[f.id] > 0)
      .map(
        (f) =>
          `<button type="button" class="chip${ui.filtr === f.id ? " aktywny" : ""}" data-akcja="filtr" data-filtr="${f.id}" aria-pressed="${ui.filtr === f.id}">${esc(f.etykieta)} <span class="licznik">${l[f.id]}</span></button>`
      )
      .join("")}</div>`;
  }
  const tresc =
    cfg.widok === "miesiac"
      ? widokMiesiaca(widoczne, dzisIso, cfg, ui, granice)
      : widokAgendy(widoczne, dzisIso, cfg, ui);
  return `<ha-card>${tytul}${wersja}<div class="podsumowanie${pod.wazne ? " wazne" : ""}">${pod.html}</div>${chipsy}<div class="tresc-karty">${tresc}</div></ha-card>`;
}

export const CSS = `
:host { display: block; }
ha-card { container-type: inline-size; padding: 12px 16px 16px; }
h2, h3, h4 { margin: 0; font-weight: 500; }
.tytul { font-size: 1.25rem; padding: 4px 0 8px; color: var(--primary-text-color); }
.podsumowanie { padding: 8px 12px; margin-bottom: 8px; border-radius: 8px; color: var(--primary-text-color);
  background: var(--secondary-background-color, rgba(127,127,127,.1)); font-size: .95rem; }
.podsumowanie.wazne { background: rgba(219,68,55,.12);
  background: color-mix(in srgb, var(--error-color, #db4437) 14%, transparent); }
.wersja { padding: 6px 12px; margin-bottom: 8px; border-radius: 8px; font-size: .85rem;
  background: rgba(255,166,0,.18); color: var(--primary-text-color); }
.chipsy { display: flex; flex-wrap: wrap; gap: 6px; margin: 4px 0 8px; }
.chip { min-height: 40px; padding: 0 12px; border-radius: 20px; cursor: pointer; font: inherit; font-size: .85rem;
  border: 1px solid var(--divider-color, #ccc); background: transparent; color: var(--primary-text-color); }
.chip.aktywny { background: var(--primary-color, #03a9f4); border-color: var(--primary-color, #03a9f4);
  color: var(--text-primary-color, #fff); }
.chip .licznik { opacity: .75; margin-left: 2px; }
button:focus-visible { outline: 2px solid var(--primary-color, #03a9f4); outline-offset: 2px; }
.tydzien-naglowek { margin: 12px 0 4px; font-size: .75rem; letter-spacing: .06em; text-transform: uppercase;
  color: var(--secondary-text-color); }
.dzien { margin-bottom: 8px; }
.dzien-naglowek { display: flex; align-items: baseline; gap: 8px; padding: 6px 8px; border-radius: 6px;
  font-size: 1rem; color: var(--primary-text-color); }
.dzien-naglowek .data { color: var(--secondary-text-color); font-size: .85rem; font-weight: 400; }
.dzien-naglowek .odl { margin-left: auto; color: var(--secondary-text-color); font-size: .8rem; font-weight: 400; }
.dzien.ma-sprawdzian .dzien-naglowek { border-left: 4px solid var(--error-color, #db4437); font-weight: 700; }
.dzien.wolne .dzien-naglowek { background: rgba(67,160,71,.15);
  background: color-mix(in srgb, var(--success-color, #43a047) 15%, transparent); }
.lista { list-style: none; margin: 0; padding: 0; }
.typ-sprawdzian { --kolor: var(--error-color, #db4437); }
.typ-kartkowka { --kolor: var(--warning-color, #ffa600); }
.typ-dzien_wolny { --kolor: var(--success-color, #43a047); }
.typ-wycieczka { --kolor: var(--info-color, #4285f4); }
.typ-odwolane { --kolor: var(--disabled-text-color, #9e9e9e); }
.typ-rada, .typ-zebranie, .typ-inne { --kolor: var(--secondary-text-color, #727272); }
.zd { display: flex; gap: 10px; align-items: flex-start; margin: 4px 0; padding: 8px 10px;
  border-left: 4px solid var(--kolor); border-radius: 0 8px 8px 0; color: var(--primary-text-color); }
.zd.typ-sprawdzian { background: rgba(219,68,55,.1);
  background: color-mix(in srgb, var(--error-color, #db4437) 10%, transparent); }
.zd.kompakt { align-items: center; padding: 4px 10px; margin: 2px 0; }
.ikona { font-size: 1.2rem; line-height: 1.4; }
.tresc { min-width: 0; flex: 1; }
.linia { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; }
.glowna { font-weight: 500; }
.typ-sprawdzian .glowna { font-weight: 700; }
.typ-odwolane .glowna { text-decoration: line-through; color: var(--secondary-text-color); }
.odznaka { padding: 1px 8px; border-radius: 10px; font-size: .7rem; font-weight: 600; letter-spacing: .04em;
  text-transform: uppercase; color: var(--kolor); border: 1px solid var(--kolor); }
.typ-sprawdzian .odznaka { background: var(--error-color, #db4437); color: #fff; }
.meta { color: var(--secondary-text-color); font-size: .8rem; margin-left: auto; }
.tresc .meta { margin-left: 0; margin-top: 2px; }
.opis { display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden;
  width: 100%; margin: 4px 0 0; padding: 0; text-align: left; cursor: pointer; font: inherit; font-size: .85rem;
  border: 0; background: none; color: var(--secondary-text-color); }
.opis.rozwiniety { display: block; -webkit-line-clamp: unset; }
.wiecej { margin-top: 8px; min-height: 40px; padding: 0 16px; border-radius: 20px; cursor: pointer; font: inherit;
  border: 1px solid var(--divider-color, #ccc); background: transparent; color: var(--primary-color); }
.pusto { padding: 16px 8px; text-align: center; color: var(--secondary-text-color); }
.mies-nawigacja { display: flex; align-items: center; justify-content: space-between; margin-bottom: 8px; }
.mies-tytul { font-weight: 500; text-transform: capitalize; color: var(--primary-text-color); }
.strzalka { width: 40px; height: 40px; border-radius: 50%; cursor: pointer; font-size: 1.3rem;
  border: 0; background: none; color: var(--primary-text-color); }
.strzalka[disabled] { opacity: .3; cursor: default; }
.siatka { display: grid; grid-template-columns: repeat(7, 1fr); gap: 2px; }
.dn { text-align: center; font-size: .75rem; padding: 4px 0; color: var(--secondary-text-color); }
.komorka { min-height: 48px; padding: 4px 2px; display: flex; flex-direction: column; align-items: center; gap: 2px;
  cursor: pointer; font: inherit; border: 1px solid transparent; border-radius: 8px; background: none;
  color: var(--primary-text-color); }
.komorka.obcy { opacity: .35; }
.komorka.przeszly { opacity: .5; }
.komorka.dzis { border-color: var(--primary-color, #03a9f4); }
.komorka.wybrany { background: var(--secondary-background-color, rgba(127,127,127,.15)); }
.komorka.ma-sprawdzian .num { font-weight: 700; color: var(--error-color, #db4437); }
.kropki { display: flex; gap: 3px; align-items: center; min-height: 10px; }
.kropka { display: inline-block; width: 6px; height: 6px; border-radius: 50%; background: var(--kolor); }
.kropka.duza { width: 9px; height: 9px; box-shadow: 0 0 0 2px rgba(219,68,55,.3); }
.plus { font-size: .65rem; color: var(--secondary-text-color); }
.wybrany-dzien { margin-top: 12px; }
@container (max-width: 380px) {
  .zd { padding: 6px 8px; }
  .opis { -webkit-line-clamp: 1; }
  .dzien-naglowek .data { display: none; }
  .kompakt .meta { display: none; }
}
@media (prefers-reduced-motion: no-preference) {
  .chip, .komorka { transition: background-color .15s; }
}
`;

// ---------- element karty ----------

const Baza = typeof HTMLElement !== "undefined" ? HTMLElement : class {};

function dzisLokalnie() {
  return dataIso(new Date());
}

export class LibrusTerminarzCard extends Baza {
  constructor() {
    super();
    this._cfg = null;
    this._hass = null;
    this._podpis = "";
    this._timer = null;
    this._ui = { filtr: "wszystko", rozwiniete: new Set(), pokazWszystko: false, miesiac: null, wybranyDzien: null };
    if (this.attachShadow) this.attachShadow({ mode: "open" });
  }

  static getConfigElement() {
    return document.createElement("librus-terminarz-card-editor");
  }

  static getStubConfig(hass) {
    const [entity] = znajdzEncjeTerminarza(hass);
    return { type: "custom:librus-terminarz-card", ...(entity ? { entity } : {}) };
  }

  setConfig(config) {
    this._cfg = normalizujKonfig(config);
    this._podpis = "";
    this._ui.miesiac = null;
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    const id = this._encja();
    const st = id ? hass?.states?.[id] : null;
    const podpis = `${id}|${st?.last_updated ?? ""}|${st?.state ?? ""}`;
    if (podpis !== this._podpis) {
      this._podpis = podpis;
      this._render();
    }
  }

  getCardSize() {
    return this._cfg?.widok === "miesiac" ? 8 : 6;
  }

  getGridOptions() {
    return { columns: 12, min_columns: 6 };
  }

  connectedCallback() {
    this._zaplanujPolnoc();
    if (this.shadowRoot && !this._klik) {
      this._klik = (e) => this._obsluzKlik(e);
      this.shadowRoot.addEventListener("click", this._klik);
    }
  }

  disconnectedCallback() {
    clearTimeout(this._timer);
    this._timer = null;
  }

  _zaplanujPolnoc() {
    clearTimeout(this._timer);
    const teraz = new Date();
    const polnoc = new Date(teraz.getFullYear(), teraz.getMonth(), teraz.getDate() + 1, 0, 0, 5);
    this._timer = setTimeout(() => {
      this._render();
      this._zaplanujPolnoc();
    }, polnoc - teraz);
  }

  _encja() {
    if (this._cfg?.entity) return this._cfg.entity;
    return this._hass ? znajdzEncjeTerminarza(this._hass)[0] ?? null : null;
  }

  _obsluzKlik(e) {
    const el = e.target?.closest?.("[data-akcja]");
    if (!el || el.disabled) return;
    const ui = this._ui;
    switch (el.dataset.akcja) {
      case "filtr":
        ui.filtr = el.dataset.filtr;
        break;
      case "opis":
        ui.rozwiniete.has(el.dataset.id) ? ui.rozwiniete.delete(el.dataset.id) : ui.rozwiniete.add(el.dataset.id);
        break;
      case "wiecej":
        ui.pokazWszystko = true;
        break;
      case "dzien":
        ui.wybranyDzien = ui.wybranyDzien === el.dataset.data ? null : el.dataset.data;
        break;
      case "mies": {
        const n = ui.miesiac.rok * 12 + ui.miesiac.mies + Number(el.dataset.kierunek);
        ui.miesiac = { rok: Math.floor(n / 12), mies: n % 12 };
        ui.wybranyDzien = null;
        break;
      }
      default:
        return;
    }
    this._render();
  }

  _model() {
    const cfg = this._cfg;
    const dzisIso = dzisLokalnie();
    const id = this._encja();
    const st = id ? this._hass?.states?.[id] : null;
    let blad = null;
    let zdarzenia = [];
    let wersjaIntegracji = null;
    let zakresDo = null;
    if (!this._hass) blad = "Wczytywanie…";
    else if (!id) blad = "Nie znaleziono sensora Terminarz. Ustaw pole „entity”.";
    else if (!st || st.state === "unavailable" || st.state === "unknown") blad = `Encja ${id} jest niedostępna`;
    else {
      zdarzenia = normalizujZdarzenia(st.attributes?.zdarzenia, dzisIso);
      wersjaIntegracji = st.attributes?.wersja_integracji ?? null;
      zakresDo = st.attributes?.zakres_do ?? null;
    }
    const teraz = parsujIso(dzisIso);
    if (!this._ui.miesiac) this._ui.miesiac = { rok: teraz.getFullYear(), mies: teraz.getMonth() };
    const ostatni = parsujIso(zakresDo) ?? parsujIso(zdarzenia[zdarzenia.length - 1]?.data) ?? teraz;
    const min = teraz.getFullYear() * 12 + teraz.getMonth();
    const granice = { min, max: Math.max(min + 1, ostatni.getFullYear() * 12 + ostatni.getMonth()) };
    return { cfg, zdarzenia, dzisIso, ui: this._ui, blad, wersjaIntegracji, granice };
  }

  _render() {
    if (!this._cfg || !this.shadowRoot) return;
    this.shadowRoot.innerHTML = `<style>${CSS}</style>${budujHtml(this._model())}`;
  }
}

// ---------- edytor wizualny ----------

export const EDITOR_SCHEMA = [
  { name: "entity", selector: { entity: { integration: "librus_apix", domain: "sensor" } } },
  { name: "tytul", selector: { text: {} } },
  {
    name: "widok",
    selector: {
      select: {
        mode: "dropdown",
        options: [
          { value: "agenda", label: "Agenda (lista po dniach)" },
          { value: "miesiac", label: "Miesiąc (kalendarz)" },
        ],
      },
    },
  },
  { name: "dni", selector: { number: { min: 1, max: 365, mode: "box" } } },
  {
    name: "typy",
    selector: {
      select: {
        multiple: true,
        mode: "list",
        options: WSZYSTKIE_TYPY.map((t) => ({ value: t, label: `${TYPY[t].ikona} ${TYPY[t].etykieta || "Inne"}` })),
      },
    },
  },
  { name: "filtry", selector: { boolean: {} } },
  { name: "kompakt", selector: { boolean: {} } },
  { name: "pokaz_opis", selector: { boolean: {} } },
  { name: "pokaz_nauczyciela", selector: { boolean: {} } },
  { name: "max_zdarzen", selector: { number: { min: 0, max: 200, mode: "box" } } },
];

export const ETYKIETY_EDYTORA = {
  entity: "Sensor terminarza (puste = wykryj automatycznie)",
  tytul: "Tytuł",
  widok: "Widok",
  dni: "Horyzont agendy (dni)",
  typy: "Pokazuj tylko typy (puste = wszystkie)",
  filtry: "Chipsy filtrów",
  kompakt: "Tryb kompaktowy",
  pokaz_opis: "Pokaż opis",
  pokaz_nauczyciela: "Pokaż nauczyciela",
  max_zdarzen: "Limit zdarzeń (0 = bez limitu)",
};

export class LibrusTerminarzCardEditor extends Baza {
  setConfig(config) {
    this._config = config;
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    if (this._form) this._form.hass = hass;
  }

  _render() {
    if (!this._form) {
      this._form = document.createElement("ha-form");
      this._form.computeLabel = (s) => ETYKIETY_EDYTORA[s.name] ?? s.name;
      this._form.schema = EDITOR_SCHEMA;
      this._form.addEventListener("value-changed", (e) => {
        const config = { ...e.detail.value };
        for (const k of Object.keys(config)) if (config[k] === "" || config[k] === undefined) delete config[k];
        this.dispatchEvent(new CustomEvent("config-changed", { detail: { config }, bubbles: true, composed: true }));
      });
      this.appendChild(this._form);
    }
    this._form.hass = this._hass;
    this._form.data = { widok: "agenda", dni: 30, filtry: true, pokaz_opis: true, ...this._config };
  }
}

if (typeof customElements !== "undefined") {
  if (!customElements.get("librus-terminarz-card")) customElements.define("librus-terminarz-card", LibrusTerminarzCard);
  if (!customElements.get("librus-terminarz-card-editor")) {
    customElements.define("librus-terminarz-card-editor", LibrusTerminarzCardEditor);
  }
  globalThis.customCards = globalThis.customCards || [];
  if (!globalThis.customCards.some((c) => c.type === "librus-terminarz-card")) {
    globalThis.customCards.push({
      type: "librus-terminarz-card",
      name: "Librus – terminarz",
      description: "Terminarz Librus: sprawdziany, kartkówki i wydarzenia pogrupowane po dniach",
      preview: true,
    });
  }
}
