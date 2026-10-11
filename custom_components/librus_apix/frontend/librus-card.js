/*
 * Librus – plan i zadania: karta Lovelace `custom:librus-card`
 * dla integracji Home Assistant "Librus Synergia HA".
 *
 * Czysty JS bez zależności i bez builda. Plik działa w przeglądarce
 * (ładowany jako zasób `type: module`) oraz w Node (testy czystych funkcji).
 * Klasa karty rejestrowana jest tylko, gdy istnieje `customElements`.
 *
 * Zasada bezpieczeństwa: każda wartość pochodząca z danych (stany, atrybuty,
 * konfiguracja, odpowiedź usługi) trafia do HTML wyłącznie przez `esc()`.
 */

export const CARD_VERSION = "1.3.0";

const KLUCZ_UCZNIA = "librus-card:uczen";
export const WIDOKI = ["dzis", "jutro", "tydzien", "zadania", "plecak"];

const DNI = ["poniedziałek", "wtorek", "środa", "czwartek", "piątek", "sobota", "niedziela"];
const SKROTY_DNI = ["Pn", "Wt", "Śr", "Cz", "Pt", "So", "Nd"];
const DNI_BIERNIK = {
  poniedzialek: "W poniedziałek",
  wtorek: "We wtorek",
  sroda: "W środę",
  czwartek: "W czwartek",
  piatek: "W piątek",
  sobota: "W sobotę",
  niedziela: "W niedzielę",
};

/* ------------------------------------------------------------------ */
/* Czyste funkcje pomocnicze (eksportowane do testów)                  */
/* ------------------------------------------------------------------ */

const ESC_MAPA = {
  "&": "&amp;",
  "<": "&lt;",
  ">": "&gt;",
  '"': "&quot;",
  "'": "&#39;",
  "`": "&#96;",
};

/** Escapuje dowolną wartość do bezpiecznego wstawienia w HTML (treść i atrybuty w cudzysłowach). */
export function esc(wartosc) {
  if (wartosc === null || wartosc === undefined) return "";
  return String(wartosc).replace(/[&<>"'`]/g, (z) => ESC_MAPA[z]);
}

/** Małe litery, bez polskich znaków, tylko [a-z0-9] i pojedyncze spacje. */
export function normalizuj(tekst) {
  return String(tekst ?? "")
    .toLowerCase()
    .replace(/ł/g, "l")
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .replace(/[^a-z0-9]+/g, " ")
    .trim();
}

// Reguły dopasowania przedmiotów po rdzeniu (kolejność ma znaczenie).
const REGULY_PRZEDMIOTOW = [
  { re: /wychowanie fizyczne|(^| )w ?f( |$)/, emoji: "⚽", ton: 25, skrot: "WF" },
  { re: /edukacja dla bezpieczenstwa|(^| )edb( |$)/, emoji: "🩹", ton: 5, skrot: "EDB" },
  { re: /zajecia z wychowawca|godzina z wychowawca|wychowawcz/, emoji: "👥", ton: 280, skrot: "Wych." },
  { re: /matemat/, emoji: "🔢", ton: 210, skrot: "Mat." },
  { re: /polski/, emoji: "📖", ton: 0, skrot: "J. pol." },
  { re: /angiel/, emoji: "🇬🇧", ton: 230, skrot: "J. ang." },
  { re: /niemiec/, emoji: "🇩🇪", ton: 45, skrot: "J. niem." },
  { re: /francus/, emoji: "🇫🇷", ton: 250, skrot: "J. fr." },
  { re: /hiszpan/, emoji: "🇪🇸", ton: 30, skrot: "J. hiszp." },
  { re: /wiedza o spoleczenstwie|(^| )wos( |$)/, emoji: "⚖️", ton: 190, skrot: "WOS" },
  { re: /histori/, emoji: "🏛️", ton: 35, skrot: "Hist." },
  { re: /geograf/, emoji: "🌍", ton: 160, skrot: "Geogr." },
  { re: /biolog/, emoji: "🌿", ton: 120, skrot: "Biol." },
  { re: /przyrod/, emoji: "🌿", ton: 100, skrot: "Przyr." },
  { re: /chemi/, emoji: "🧪", ton: 290, skrot: "Chem." },
  { re: /fizyk/, emoji: "⚛️", ton: 260, skrot: "Fiz." },
  { re: /informat/, emoji: "💻", ton: 200, skrot: "Inf." },
  { re: /techni/, emoji: "🔧", ton: 20, skrot: "Techn." },
  { re: /plastyk/, emoji: "🎨", ton: 320, skrot: "Plast." },
  { re: /muzyk/, emoji: "🎵", ton: 340, skrot: "Muz." },
  { re: /religi/, emoji: "✝️", ton: 50, skrot: "Rel." },
  { re: /etyk/, emoji: "🤔", ton: 170, skrot: "Etyka" },
];

function regulaPrzedmiotu(nazwa) {
  const n = normalizuj(nazwa);
  if (!n) return null;
  return REGULY_PRZEDMIOTOW.find((r) => r.re.test(n)) || null;
}

function hashTekstu(tekst) {
  let h = 5381;
  for (const z of String(tekst)) h = ((h * 33) ^ z.codePointAt(0)) >>> 0;
  return h;
}

/** Dopuszcza tylko bezpieczne znaki w wartości koloru (wstawiany do atrybutu style). */
function bezpiecznyKolor(kolor) {
  const k = String(kolor ?? "").trim();
  return /^[#\w\s%.,()/+-]{1,60}$/.test(k) ? k : "";
}

function znajdzNadpisanie(nazwa, nadpisania) {
  if (!nadpisania || typeof nadpisania !== "object") return null;
  if (Object.prototype.hasOwnProperty.call(nadpisania, nazwa)) return nadpisania[nazwa];
  const n = normalizuj(nazwa);
  for (const [klucz, wartosc] of Object.entries(nadpisania)) {
    if (normalizuj(klucz) === n) return wartosc;
  }
  return null;
}

/**
 * Styl przedmiotu: emoji, kolor ("H S% L%" lub kolor CSS z nadpisania),
 * gotowe tło (półprzezroczyste – czytelne w jasnym i ciemnym motywie) i akcent.
 */
export function stylPrzedmiotu(nazwa, nadpisania) {
  const regula = regulaPrzedmiotu(nazwa);
  const nad = znajdzNadpisanie(nazwa, nadpisania) || {};
  const emoji = nad.emoji ? String(nad.emoji) : regula ? regula.emoji : "📚";
  let kolor = bezpiecznyKolor(nad.kolor);
  if (!kolor) {
    const ton = regula ? regula.ton : hashTekstu(normalizuj(nazwa) || "?") % 360;
    kolor = `${ton} 65% 50%`;
  }
  const trojka = /^\d/.test(kolor); // format "H S% L%"
  const tlo = trojka ? `hsl(${kolor} / 0.18)` : `color-mix(in srgb, ${kolor} 18%, transparent)`;
  const akcent = trojka ? `hsl(${kolor})` : kolor;
  return { emoji, kolor, tlo, akcent, znany: Boolean(regula) };
}

const SPOJNIKI = new Set(["i", "z", "o", "w", "we", "dla", "na", "do", "ze"]);

/** Krótka nazwa do siatki, np. "Mat.", "J. pol."; nieznane – inicjały lub ucięcie. */
export function skrotPrzedmiotu(nazwa, maxLen = 8) {
  const tekst = String(nazwa ?? "").trim().replace(/\s+/g, " ");
  if (!tekst) return "";
  const max = Math.max(2, Number(maxLen) || 8);
  const regula = regulaPrzedmiotu(tekst);
  if (regula && regula.skrot.length <= max) return regula.skrot;
  if (tekst.length <= max) return tekst;
  const slowa = tekst.split(" ").filter((s) => !SPOJNIKI.has(s.toLowerCase()));
  if (slowa.length >= 2) return slowa.map((s) => s[0].toUpperCase()).join("").slice(0, max);
  return tekst.slice(0, max - 1).trimEnd() + ".";
}

/** "08:05" -> 485; niepoprawne -> NaN. */
export function minuty(godzina) {
  const m = /^(\d{1,2}):(\d{2})/.exec(String(godzina ?? ""));
  return m ? Number(m[1]) * 60 + Number(m[2]) : NaN;
}

/**
 * Ustala, co się dzieje teraz na lekcjach (odwołane są pomijane).
 * now: Date lub "HH:MM". Zwraca {stan: brak|przed|trwa|przerwa|po, lekcja, nastepna}.
 */
export function aktualnaLekcja(lekcje, now) {
  const t = typeof now === "string" ? minuty(now) : now.getHours() * 60 + now.getMinutes();
  const lista = (Array.isArray(lekcje) ? lekcje : [])
    .filter((l) => l && !l.odwolana && !isNaN(minuty(l.od)) && !isNaN(minuty(l.do)))
    .sort((a, b) => minuty(a.od) - minuty(b.od) || (a.numer ?? 0) - (b.numer ?? 0));
  if (!lista.length) return { stan: "brak", lekcja: null, nastepna: null };
  for (let i = 0; i < lista.length; i++) {
    const l = lista[i];
    if (t < minuty(l.od)) {
      return { stan: i === 0 ? "przed" : "przerwa", lekcja: null, nastepna: l };
    }
    if (t < minuty(l.do)) {
      const nast = lista.slice(i + 1).find((x) => minuty(x.od) >= minuty(l.do)) || null;
      return { stan: "trwa", lekcja: l, nastepna: nast };
    }
  }
  return { stan: "po", lekcja: null, nastepna: null };
}

/** Luki w numeracji lekcji danego dnia (okienka). */
export function okienka(lekcje) {
  const lista = (Array.isArray(lekcje) ? lekcje : []).filter((l) => l && Number.isInteger(l.numer));
  const numery = [...new Set(lista.map((l) => l.numer))].sort((a, b) => a - b);
  const wynik = [];
  for (let i = 0; i + 1 < numery.length; i++) {
    const a = numery[i];
    const b = numery[i + 1];
    if (b - a > 1) {
      const poprz = lista.find((l) => l.numer === a);
      const nast = lista.find((l) => l.numer === b);
      const brakujace = [];
      for (let n = a + 1; n < b; n++) brakujace.push(n);
      wynik.push({ po: a, przed: b, numery: brakujace, od: poprz?.do ?? null, do: nast?.od ?? null });
    }
  }
  return wynik;
}

/* ---- daty (ISO RRRR-MM-DD, liczone w UTC, żeby uniknąć problemów z DST) ---- */

function isoNaMs(iso) {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(String(iso ?? ""));
  return m ? Date.UTC(Number(m[1]), Number(m[2]) - 1, Number(m[3])) : NaN;
}
function msNaIso(ms) {
  return new Date(ms).toISOString().slice(0, 10);
}
export function dodajDni(iso, n) {
  const ms = isoNaMs(iso);
  return isNaN(ms) ? null : msNaIso(ms + n * 86400000);
}
/** 0 = poniedziałek … 6 = niedziela */
export function dzienTygodnia(iso) {
  const ms = isoNaMs(iso);
  return isNaN(ms) ? -1 : (new Date(ms).getUTCDay() + 6) % 7;
}
export function poniedzialekTygodnia(iso) {
  const d = dzienTygodnia(iso);
  return d < 0 ? null : dodajDni(iso, -d);
}
/** Lokalna data jako ISO (nie UTC!). */
export function dataIso(data = new Date()) {
  const p = (n) => String(n).padStart(2, "0");
  return `${data.getFullYear()}-${p(data.getMonth() + 1)}-${p(data.getDate())}`;
}
/** "2025-10-13" -> "13.10" */
export function fmtData(iso) {
  const m = /^\d{4}-(\d{2})-(\d{2})/.exec(String(iso ?? ""));
  return m ? `${m[2]}.${m[1]}` : "";
}

/** Przesuwa tydzień o `delta` tygodni; wynik zawsze jest poniedziałkiem. */
export function przesunTydzien(poniedzialekIso, delta) {
  const pon = poniedzialekTygodnia(poniedzialekIso);
  return pon ? dodajDni(pon, 7 * (Number(delta) || 0)) : null;
}

/** Okno dostępnych tygodni względem bieżącego: {biezacy, od, do} (poniedziałki). */
export function oknoTygodni(dzisIso, wstecz = 2, naprzod = 4) {
  const biezacy = poniedzialekTygodnia(dzisIso);
  return {
    biezacy,
    od: przesunTydzien(biezacy, -wstecz),
    do: przesunTydzien(biezacy, naprzod),
  };
}

export function wOknie(poniedzialekIso, okno) {
  return Boolean(poniedzialekIso && okno && poniedzialekIso >= okno.od && poniedzialekIso <= okno.do);
}

/**
 * Siatka tygodnia: kolumny = dni (Pn–Pt zawsze, So/Nd tylko z lekcjami),
 * wiersze = numery lekcji. Komórka: {lekcje:[...], luka:bool, okienko:bool}.
 */
export function zbudujSiatke(dni, numeryLekcji) {
  const listaDni = Array.isArray(dni) ? dni : [];
  const kolumny = [];
  listaDni.forEach((d, i) => {
    if (!d) return;
    const dt = d.data ? dzienTygodnia(d.data) : i;
    const weekend = dt >= 5;
    const maLekcje = (Array.isArray(d.lekcje) && d.lekcje.length > 0) || Number(d.liczba_lekcji) > 0;
    if (!weekend || maLekcje) {
      kolumny.push({
        indeks: i,
        data: d.data ?? null,
        skrot: d.skrot || SKROTY_DNI[dt] || "",
        dzien: d,
      });
    }
  });

  const numery = new Set((Array.isArray(numeryLekcji) ? numeryLekcji : []).filter(Number.isInteger));
  for (const k of kolumny) {
    for (const l of k.dzien.lekcje || []) if (Number.isInteger(l?.numer)) numery.add(l.numer);
  }
  const posortowane = [...numery].sort((a, b) => a - b);

  const zakresy = kolumny.map((k) => {
    const n = (k.dzien.lekcje || []).map((l) => l?.numer).filter(Number.isInteger);
    return n.length ? [Math.min(...n), Math.max(...n)] : null;
  });

  const wiersze = posortowane.map((numer) => {
    let od = null;
    let do_ = null;
    const komorki = kolumny.map((k, ki) => {
      const lekcje = (k.dzien.lekcje || []).filter((l) => l?.numer === numer);
      if (lekcje.length && !od) {
        od = lekcje[0].od ?? null;
        do_ = lekcje[0].do ?? null;
      }
      const z = zakresy[ki];
      const luka = lekcje.length === 0;
      return { lekcje, luka, okienko: luka && Boolean(z) && numer > z[0] && numer < z[1] };
    });
    return { numer, od, do: do_, komorki };
  });

  return { kolumny, wiersze };
}

/**
 * Etykieta dnia: "Dzisiaj", "Jutro" albo "W poniedziałek" / "We wtorek"…
 * dzien: obiekt Dnia ({data, dzien}) lub nazwa dnia.
 */
export function etykietaDnia(dzien, czyJutro, dzisIso) {
  const d = typeof dzien === "string" ? { dzien } : dzien || {};
  if (d.data && dzisIso && d.data === dzisIso) return "Dzisiaj";
  if (czyJutro === true) return "Jutro";
  if (d.data && dzisIso && d.data === dodajDni(dzisIso, 1)) return "Jutro";
  const nazwa = d.dzien || (d.data ? DNI[dzienTygodnia(d.data)] : "");
  if (!nazwa) return "";
  return DNI_BIERNIK[normalizuj(nazwa)] || `W ${nazwa}`;
}

const GRUPY_ZADAN = ["dzis", "jutro", "tydzien", "pozniej", "po_terminie"];

function pilnoscZadania(z) {
  switch (z.pilnosc) {
    case "dzis":
    case "jutro":
    case "tydzien":
    case "pozniej":
    case "po_terminie":
      return z.pilnosc;
    case "brak_terminu":
      return "pozniej";
    default:
      break;
  }
  const d = z.dni_do;
  if (!Number.isInteger(d)) return "pozniej";
  if (d < 0) return "po_terminie";
  if (d === 0) return "dzis";
  if (d === 1) return "jutro";
  if (d <= 7) return "tydzien";
  return "pozniej";
}

/** Grupuje zadania wg `pilnosc` (bez duplikatów po id, posortowane po terminie). */
export function grupujZadania(zadania) {
  const grupy = Object.fromEntries(GRUPY_ZADAN.map((g) => [g, []]));
  const widziane = new Set();
  for (const z of Array.isArray(zadania) ? zadania : []) {
    if (!z || typeof z !== "object") continue;
    if (z.id !== undefined && z.id !== null) {
      if (widziane.has(z.id)) continue;
      widziane.add(z.id);
    }
    grupy[pilnoscZadania(z)].push(z);
  }
  const porownaj = (a, b) => {
    const ta = a.termin || "9999-99-99";
    const tb = b.termin || "9999-99-99";
    if (ta !== tb) return ta < tb ? -1 : 1;
    return String(a.przedmiot ?? "").localeCompare(String(b.przedmiot ?? ""), "pl");
  };
  for (const g of GRUPY_ZADAN) grupy[g].sort(porownaj);
  return grupy;
}

/** Identyfikatory encji ucznia. */
export function entityIds(slug) {
  const s = String(slug ?? "").trim().toLowerCase();
  const p = `sensor.librus_${s}_`;
  return {
    plan_dzis: `${p}plan_dzis`,
    plan_jutro: `${p}plan_jutro`,
    nastepna_lekcja: `${p}nastepna_lekcja`,
    plan_tygodnia: `${p}plan_tygodnia`,
    do_zrobienia_jutro: `${p}do_zrobienia_jutro`,
    zadania_otwarte: `${p}zadania_otwarte`,
  };
}

/** Normalizuje listę uczniów z konfiguracji i wybiera aktywnego (zapisany slug lub pierwszy). */
export function wybierzUcznia(config, zapisany) {
  const zrodlo =
    Array.isArray(config?.uczniowie) && config.uczniowie.length
      ? config.uczniowie
      : config?.slug
        ? [{ slug: config.slug }]
        : [];
  const uczniowie = zrodlo
    .map((u) => (typeof u === "string" ? { slug: u } : u))
    .filter((u) => u && u.slug !== undefined && String(u.slug).trim())
    .map((u) => {
      const slug = String(u.slug).trim().toLowerCase();
      return {
        slug,
        nazwa: u.nazwa ? String(u.nazwa) : slug.charAt(0).toUpperCase() + slug.slice(1),
        numerek: u.numerek || null,
        numer_w_dzienniku: u.numer_w_dzienniku ?? null,
      };
    });
  const wybrany = uczniowie.find((u) => u.slug === zapisany) || uczniowie[0] || null;
  return { uczniowie, wybrany };
}

/** Slug z pierwszego sensora `sensor.librus_<slug>_plan_tygodnia`. */
export function wyprowadzSlug(states) {
  for (const id of Object.keys(states || {})) {
    const m = /^sensor\.librus_(.+)_plan_tygodnia$/.exec(id);
    if (m) return m[1];
  }
  return null;
}

/** true, gdy wersja karty różni się od wersji integracji (i obie są znane). */
export function czyInnaWersja(wersjaKarty, wersjaIntegracji) {
  return Boolean(wersjaKarty && wersjaIntegracji && String(wersjaKarty) !== String(wersjaIntegracji));
}

/* ------------------------------------------------------------------ */
/* Fragmenty HTML (zawsze przez esc)                                   */
/* ------------------------------------------------------------------ */

function styleKoloru(s) {
  return `--tlo:${esc(s.tlo)};--akcent:${esc(s.akcent)}`;
}

function opisZmiany(zmiana) {
  if (!zmiana || typeof zmiana !== "object") return "";
  const etykiety = { teacher_swap: "nauczyciel", subject_swap: "przedmiot", classroom_swap: "sala" };
  const fmt = (v) => {
    if (v === true) return "";
    if (Array.isArray(v)) return v.filter((x) => x !== null && x !== "").join(" → ");
    if (v && typeof v === "object") return Object.values(v).filter((x) => x !== null && x !== "").join(" → ");
    return v === null || v === undefined || v === false ? "" : String(v);
  };
  return Object.entries(zmiana)
    .filter(([, v]) => v !== null && v !== undefined && v !== false)
    .map(([k, v]) => {
      const t = fmt(v);
      return t ? `${etykiety[k] || k}: ${t}` : etykiety[k] || k;
    })
    .join("; ");
}

function chipyWydarzen(wydarzenia) {
  const lista = Array.isArray(wydarzenia) ? wydarzenia.filter(Boolean) : [];
  if (!lista.length) return "";
  return `<div class="chipy-wydarzen">${lista
    .map(
      (w) =>
        `<span class="chip chip-${esc(w.typ)}" title="${esc(w.przedmiot)}">${esc(w.ikona || "📌")} ${esc(w.tytul)}</span>`,
    )
    .join("")}</div>`;
}

function plakietki(l, kompakt = false) {
  const out = [];
  const zadania = Array.isArray(l.zadania) ? l.zadania : [];
  if (l.odwolana) out.push(["odwolana", "❌", "odwołana", ""]);
  if (l.sprawdzian) {
    const tyt = (l.wydarzenia || []).filter((w) => w && w.typ === "sprawdzian").map((w) => w.tytul).join("; ");
    out.push(["spr", "📝", "sprawdzian", tyt]);
  } else if ((l.wydarzenia || []).some((w) => w && w.typ === "kartkowka")) {
    out.push(["spr", "✏️", "kartkówka", ""]);
  }
  if (zadania.length) {
    const tresc = zadania.map((z) => [z.kategoria, z.tresc].filter(Boolean).join(": ")).join("\n");
    out.push(["zad", "🏠", zadania.length > 1 ? `zadania (${zadania.length})` : "zadanie", tresc]);
  }
  if (l.zastepstwo) out.push(["zast", "⚠", "zastępstwo", opisZmiany(l.zmiana)]);
  if (!out.length) return "";
  if (kompakt) {
    return `<span class="ikony">${out
      .map(([k, ikona, tekst, tip]) => `<span class="ik ik-${k}" title="${esc(tip || tekst)}">${esc(ikona)}</span>`)
      .join("")}</span>`;
  }
  return `<div class="plakietki">${out
    .map(
      ([k, ikona, tekst, tip]) =>
        `<span class="plakietka pl-${k}"${tip ? ` title="${esc(tip)}"` : ""}>${esc(ikona)} ${esc(tekst)}</span>`,
    )
    .join("")}</div>`;
}

function szczegolyLekcji(l, przedmioty) {
  const s = stylPrzedmiotu(l.przedmiot, przedmioty);
  const wiersze = [];
  wiersze.push(
    `<div class="sz-tyt" style="${styleKoloru(s)}"><span class="emoji">${esc(s.emoji)}</span> <b class="${
      l.odwolana ? "przekreslone" : ""
    }">${esc(l.przedmiot)}</b></div>`,
  );
  wiersze.push(`<div class="sz-meta">Lekcja ${esc(l.numer)} · ${esc(l.od)}–${esc(l.do)}</div>`);
  const meta = [];
  if (l.nauczyciel) meta.push(`👤 ${esc(l.nauczyciel)}`);
  if (l.sala) meta.push(`🚪 ${esc(opisSali(l.sala))}`);
  if (Array.isArray(l.grupy) && l.grupy.length) meta.push(`👥 ${esc(l.grupy.join(", "))}`);
  if (meta.length) wiersze.push(`<div class="sz-meta">${meta.join(" · ")}</div>`);
  wiersze.push(plakietki(l));
  if (l.zastepstwo && opisZmiany(l.zmiana)) wiersze.push(`<div class="podtekst">⚠ ${esc(opisZmiany(l.zmiana))}</div>`);
  if (l.info) wiersze.push(`<div class="podtekst">ℹ️ ${esc(l.info)}</div>`);
  for (const z of l.zadania || []) {
    wiersze.push(
      `<div class="podtekst">🏠 <b>${esc(z.kategoria || "Zadanie")}</b>${z.tresc ? `: ${esc(z.tresc)}` : ""}</div>`,
    );
  }
  for (const w of l.wydarzenia || []) {
    if (!w) continue;
    wiersze.push(`<div class="podtekst">${esc(w.ikona || "📌")} ${esc(w.tytul)}</div>`);
  }
  return `<div class="szczegoly">${wiersze.join("")}</div>`;
}

/** "12" -> "sala 12"; "sala gim." bez zmian. */
function opisSali(sala) {
  const t = String(sala ?? "").trim();
  return /^sala\b/i.test(t) ? t : `sala ${t}`;
}

function komunikat(tekst, ikona = "ℹ️", klasa = "") {
  return `<div class="komunikat ${klasa}"><span class="kom-ikona">${esc(ikona)}</span><div>${tekst}</div></div>`;
}

function brakEncji(id) {
  return komunikat(
    `Nie znaleziono encji <code>${esc(id)}</code>.<br><small>Sprawdź <code>slug</code> ucznia w konfiguracji karty i czy integracja Librus działa.</small>`,
    "🔍",
  );
}

function sortujLekcje(lekcje) {
  return [...(Array.isArray(lekcje) ? lekcje : [])]
    .filter(Boolean)
    .sort((a, b) => (a.numer ?? 99) - (b.numer ?? 99) || minuty(a.od) - minuty(b.od));
}

function grupujPoNumerze(lekcje) {
  const grupy = [];
  for (const l of sortujLekcje(lekcje)) {
    const ost = grupy[grupy.length - 1];
    if (ost && ost.numer === l.numer) ost.lekcje.push(l);
    else grupy.push({ numer: l.numer, lekcje: [l] });
  }
  return grupy;
}

function opisOkienka(o) {
  const nr = o.numery.length > 1 ? `lekcje ${o.numery[0]}–${o.numery[o.numery.length - 1]}` : `lekcja ${o.numery[0]}`;
  const czas = o.od && o.do ? ` (${o.od}–${o.do})` : "";
  return `☕ okienko · ${nr}${czas}`;
}

function terminZadania(z) {
  if (!z.termin) return z.termin_raw ? String(z.termin_raw) : "bez terminu";
  const dt = dzienTygodnia(z.termin);
  let t = `${SKROTY_DNI[dt] || ""} ${fmtData(z.termin)}`.trim();
  if (Number.isInteger(z.dni_do) && z.dni_do < 0) t += ` (${-z.dni_do} dn. temu)`;
  return t;
}

function pozycjaZadania(z, przedmioty) {
  const s = stylPrzedmiotu(z.przedmiot, przedmioty);
  return `<li class="zadanie" style="${styleKoloru(s)}">
    <span class="emoji">${esc(s.emoji)}</span>
    <div class="z-tresc">
      <div><b>${esc(z.przedmiot || "Zadanie")}</b>${z.kategoria ? ` · <span class="drugorzedny">${esc(z.kategoria)}</span>` : ""}</div>
      ${z.tresc ? `<div class="z-opis">${esc(z.tresc)}</div>` : ""}
    </div>
    <div class="z-termin">${esc(terminZadania(z))}</div>
  </li>`;
}

/* ------------------------------------------------------------------ */
/* Style                                                               */
/* ------------------------------------------------------------------ */

const CSS = `
:host { display: block; }
* { box-sizing: border-box; }
.karta {
  container: librus / inline-size;
  background: var(--ha-card-background, var(--card-background-color, #fff));
  color: var(--primary-text-color, #212121);
  border-radius: var(--ha-card-border-radius, 12px);
  box-shadow: var(--ha-card-box-shadow, none);
  border: var(--ha-card-border-width, 1px) solid var(--ha-card-border-color, var(--divider-color, #e0e0e0));
  padding: 12px 14px 14px;
  font-size: 14px;
  line-height: 1.35;
  overflow: hidden;
}
button { font: inherit; color: inherit; }
code { font-size: 0.9em; }
.drugorzedny, .podtytul, .sz-meta, .godz, small { color: var(--secondary-text-color, #727272); }
.przekreslone { text-decoration: line-through; opacity: 0.7; }

.pasek-wersji {
  font-size: 12px; padding: 6px 10px; margin: -4px 0 10px; border-radius: 8px;
  background: color-mix(in srgb, var(--warning-color, #ffa600) 16%, transparent);
  border: 1px solid color-mix(in srgb, var(--warning-color, #ffa600) 45%, transparent);
}
.gora { display: flex; flex-wrap: wrap; gap: 6px; align-items: center; margin-bottom: 10px; }
.gora:empty { display: none; }
.chip-ucznia {
  border: 1px solid var(--divider-color, #e0e0e0); background: transparent; border-radius: 999px;
  padding: 4px 12px; cursor: pointer;
}
.chip-ucznia[aria-pressed="true"] {
  background: var(--primary-color, #03a9f4); border-color: var(--primary-color, #03a9f4);
  color: var(--text-primary-color, #fff);
}
.numerek { margin-left: auto; font-size: 12px; padding: 3px 10px; border-radius: 999px;
  border: 1px solid var(--divider-color, #e0e0e0); color: var(--secondary-text-color, #727272); }
.numerek.trafiony { color: var(--primary-text-color, #212121); font-weight: 600;
  background: color-mix(in srgb, var(--success-color, #43a047) 22%, transparent);
  border-color: var(--success-color, #43a047); }

.naglowek { display: flex; align-items: baseline; flex-wrap: wrap; gap: 4px 10px; margin-bottom: 8px; }
.tytul { font-size: 20px; font-weight: 600; }
.podtytul { font-size: 13px; }
.status { margin: 0 0 10px; padding: 6px 10px; border-radius: 8px; font-size: 13px;
  background: color-mix(in srgb, var(--primary-color, #03a9f4) 12%, transparent); }

.chipy-wydarzen { display: flex; flex-wrap: wrap; gap: 6px; margin: 0 0 10px; }
.chip { font-size: 12px; padding: 3px 9px; border-radius: 999px;
  background: color-mix(in srgb, var(--primary-color, #03a9f4) 14%, transparent); }
.chip-odwolane, .chip-dzien_wolny { background: color-mix(in srgb, var(--success-color, #43a047) 18%, transparent); }
.chip-sprawdzian, .chip-kartkowka { background: color-mix(in srgb, var(--error-color, #db4437) 16%, transparent); }

.kafle { display: grid; grid-template-columns: 1fr; gap: 8px; align-items: start; }
@container librus (min-width: 520px) { .kafle { grid-template-columns: repeat(auto-fill, minmax(230px, 1fr)); } }
.kafel {
  position: relative; display: grid; grid-template-columns: auto 1fr; gap: 2px 10px; padding: 10px 12px;
  border-radius: 10px; background: var(--tlo); border-left: 4px solid var(--akcent);
}
.kafel-num { grid-row: span 2; font-size: 22px; font-weight: 700; min-width: 1.4em; text-align: center; opacity: 0.85; }
.kafel-czas { font-size: 12px; color: var(--secondary-text-color, #727272); }
.kafel-glowny { font-size: 16px; font-weight: 600; }
.kafel-meta, .kafel .plakietki, .kafel .podtekst { grid-column: 2; }
.kafel-meta { font-size: 12px; color: var(--secondary-text-color, #727272); }
.kafel.odwolana .kafel-glowny { text-decoration: line-through; opacity: 0.7; }
.kafel.teraz { outline: 2px solid var(--primary-color, #03a9f4); }
.kafel.nastepna { outline: 2px dashed var(--primary-color, #03a9f4); }
.znacznik { position: absolute; top: 6px; right: 8px; font-size: 11px; font-weight: 600;
  padding: 1px 7px; border-radius: 999px; background: var(--primary-color, #03a9f4); color: var(--text-primary-color, #fff); }
.plakietki { display: flex; flex-wrap: wrap; gap: 4px; margin-top: 4px; }
.plakietka { font-size: 11px; padding: 1px 7px; border-radius: 999px; border: 1px solid var(--divider-color, #e0e0e0); }
.pl-spr { border-color: var(--error-color, #db4437); }
.pl-zast { border-color: var(--warning-color, #ffa600); }
.pl-odwolana { border-color: var(--error-color, #db4437); }
.pl-zad { border-color: var(--primary-color, #03a9f4); }
.podtekst { font-size: 12px; margin-top: 2px; overflow-wrap: anywhere; }
.okienko-wiersz { font-size: 12px; color: var(--secondary-text-color, #727272); padding: 2px 12px;
  border-top: 1px dashed var(--divider-color, #e0e0e0); border-bottom: 1px dashed var(--divider-color, #e0e0e0); }
@container librus (min-width: 520px) { .okienko-wiersz { grid-column: 1 / -1; } }

.komunikat { display: flex; gap: 10px; align-items: center; padding: 14px; border-radius: 10px;
  background: color-mix(in srgb, var(--secondary-text-color, #727272) 10%, transparent); }
.komunikat.duzy { flex-direction: column; text-align: center; font-size: 16px; padding: 22px 14px; }
.komunikat.duzy .kom-ikona { font-size: 40px; }
.kom-ikona { font-size: 22px; }
.blad { margin: 0 0 8px; padding: 6px 10px; border-radius: 8px; font-size: 13px;
  background: color-mix(in srgb, var(--error-color, #db4437) 14%, transparent);
  border: 1px solid color-mix(in srgb, var(--error-color, #db4437) 45%, transparent); }
.ostrzezenie { margin: 0 0 8px; padding: 6px 10px; border-radius: 8px; font-size: 12px;
  background: color-mix(in srgb, var(--warning-color, #ffa600) 14%, transparent); }

/* Tydzień */
.nawigacja { display: flex; align-items: center; gap: 6px; margin-bottom: 10px; }
.nawigacja .zakres { flex: 1; text-align: center; font-weight: 600; font-size: 16px; }
.nawigacja button { border: 1px solid var(--divider-color, #e0e0e0); background: transparent; border-radius: 8px;
  padding: 4px 10px; cursor: pointer; min-width: 36px; }
.nawigacja button:disabled { opacity: 0.35; cursor: default; }
.laduje { font-weight: 400; font-size: 12px; color: var(--secondary-text-color, #727272); }
.tydzien.wczytywanie .tresc-tygodnia { opacity: 0.5; pointer-events: none; }

.siatka-wrap { display: none; }
.lista-dni { display: flex; flex-direction: column; gap: 8px; }
@container librus (min-width: 520px) {
  .siatka-wrap { display: block; }
  .lista-dni { display: none; }
}
table.siatka { width: 100%; border-collapse: separate; border-spacing: 3px; table-layout: fixed; }
.siatka th, .siatka td { padding: 0; vertical-align: top; }
.siatka th.rog { width: 52px; }
.siatka thead th { font-weight: 600; font-size: 13px; }
.dzien-btn { width: 100%; border: none; background: transparent; padding: 4px 2px; border-radius: 8px; cursor: pointer; }
.dzien-btn span { font-weight: 400; color: var(--secondary-text-color, #727272); }
th.dzis .dzien-btn { background: color-mix(in srgb, var(--primary-color, #03a9f4) 20%, transparent); }
th.wolny .dzien-btn { color: var(--success-color, #43a047); }
th.nr { text-align: right; font-size: 13px; padding-right: 4px; }
th.nr .godz { font-weight: 400; font-size: 10px; }
td.dzis { background: color-mix(in srgb, var(--primary-color, #03a9f4) 6%, transparent); border-radius: 6px; }
td.okienko { background: repeating-linear-gradient(45deg, transparent 0 6px,
  color-mix(in srgb, var(--divider-color, #e0e0e0) 60%, transparent) 6px 7px); border-radius: 6px; }
.komorka { width: 100%; border: none; padding: 0; background: transparent; cursor: pointer; display: flex; flex-direction: column; gap: 2px; text-align: left; }
.komorka.wybrana .mini { outline: 2px solid var(--primary-color, #03a9f4); }
.mini { display: flex; align-items: center; gap: 4px; padding: 4px 5px; border-radius: 6px; min-height: 30px;
  background: var(--tlo); border-left: 3px solid var(--akcent); font-size: 12px; overflow: hidden; }
.mini .skrot { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; flex: 1; min-width: 0; }
.mini.odwolana .skrot { text-decoration: line-through; opacity: 0.65; }
.ikony { display: inline-flex; gap: 1px; font-size: 11px; }
.wydarzenia-linie { margin-top: 8px; font-size: 12px; display: flex; flex-direction: column; gap: 2px; }
.panel { margin-top: 10px; padding: 10px 12px; border-radius: 10px; border: 1px solid var(--divider-color, #e0e0e0); position: relative; }
.panel .zamknij { position: absolute; top: 6px; right: 6px; border: none; background: transparent; cursor: pointer; font-size: 14px; }
.panel .szczegoly + .szczegoly { margin-top: 8px; padding-top: 8px; border-top: 1px solid var(--divider-color, #e0e0e0); }
.sz-tyt { font-size: 15px; }

.dzien-karta { border: 1px solid var(--divider-color, #e0e0e0); border-radius: 10px; padding: 8px 10px; }
.dzien-karta.dzis { border-color: var(--primary-color, #03a9f4); box-shadow: inset 3px 0 0 var(--primary-color, #03a9f4); }
.dzien-karta header { display: flex; justify-content: space-between; gap: 8px; font-weight: 600; margin-bottom: 6px; }
.dzien-karta header .drugorzedny { font-weight: 400; font-size: 12px; }
.dzien-karta details { border-radius: 8px; background: var(--tlo); border-left: 3px solid var(--akcent); margin-bottom: 4px; }
.dzien-karta summary { display: flex; gap: 8px; align-items: center; padding: 6px 8px; cursor: pointer; list-style: none; }
.dzien-karta summary::-webkit-details-marker { display: none; }
.dzien-karta summary .nr { font-weight: 700; min-width: 1.2em; text-align: center; }
.dzien-karta summary .czas { font-size: 11px; color: var(--secondary-text-color, #727272); min-width: 38px; }
.dzien-karta summary .nazwa { flex: 1; min-width: 0; }
.dzien-karta details[open] .szczegoly { padding: 0 8px 8px; }
.dzien-karta .wolne { padding: 6px 0; color: var(--success-color, #43a047); font-weight: 600; }
.odwolana-tekst { text-decoration: line-through; opacity: 0.7; }

/* Zadania / plecak */
.sekcja { margin-top: 12px; }
.sekcja:first-of-type { margin-top: 0; }
.sekcja h3 { font-size: 14px; margin: 0 0 6px; font-weight: 600; }
ul.zadania { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 6px; }
.zadanie { display: flex; gap: 10px; align-items: flex-start; padding: 8px 10px; border-radius: 8px;
  background: var(--tlo); border-left: 3px solid var(--akcent); }
.zadanie .emoji { font-size: 18px; }
.z-tresc { flex: 1; min-width: 0; }
.z-opis { font-size: 13px; margin-top: 2px; overflow-wrap: anywhere; }
.z-termin { font-size: 12px; white-space: nowrap; color: var(--secondary-text-color, #727272); }
details.po-terminie > summary { cursor: pointer; font-weight: 600; color: var(--error-color, #db4437); margin: 12px 0 6px; }
.przedmioty-plecak { display: grid; grid-template-columns: repeat(auto-fill, minmax(110px, 1fr)); gap: 8px; }
.przedmiot-kafel { display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 4px;
  padding: 12px 6px; border-radius: 10px; background: var(--tlo); border: 1px solid var(--akcent); text-align: center; }
.przedmiot-kafel .emoji { font-size: 28px; }
.lista-prosta { margin: 0; padding-left: 0; list-style: none; display: flex; flex-direction: column; gap: 4px; }
`;

/* ------------------------------------------------------------------ */
/* Karta                                                               */
/* ------------------------------------------------------------------ */

const BazaHTMLElement = globalThis.HTMLElement ?? class {};

function wczytajZapisanegoUcznia() {
  try {
    return globalThis.localStorage?.getItem(KLUCZ_UCZNIA) ?? null;
  } catch (_e) {
    return null;
  }
}
function zapiszUcznia(slug) {
  try {
    globalThis.localStorage?.setItem(KLUCZ_UCZNIA, slug);
  } catch (_e) {
    /* tryb prywatny / zablokowany storage – ignorujemy */
  }
}

export class LibrusCard extends BazaHTMLElement {
  constructor() {
    super();
    this._config = null;
    this._hass = null;
    this._wybranySlug = wczytajZapisanegoUcznia();
    this._podpis = [];
    this._otwarte = new Set();
    this._resetTygodnia();
    if (this.attachShadow) {
      this.attachShadow({ mode: "open" });
      this.shadowRoot.addEventListener("click", (e) => this._klik(e));
      // toggle nie bąbelkuje – łapiemy w fazie capture, żeby pamiętać rozwinięte <details>
      this.shadowRoot.addEventListener(
        "toggle",
        (e) => {
          const k = e.target?.dataset?.klucz;
          if (!k) return;
          if (e.target.open) this._otwarte.add(k);
          else this._otwarte.delete(k);
        },
        true,
      );
    }
  }

  static getStubConfig(hass) {
    return { type: "custom:librus-card", widok: "tydzien", slug: wyprowadzSlug(hass?.states) || "uczen" };
  }

  setConfig(config) {
    if (!config || typeof config !== "object") throw new Error("Nieprawidłowa konfiguracja karty Librus.");
    const widok = config.widok ?? "tydzien";
    if (!WIDOKI.includes(widok)) {
      throw new Error(`Nieznany widok "${widok}". Dozwolone: ${WIDOKI.join(", ")}.`);
    }
    if (!wybierzUcznia(config, null).wybrany) {
      throw new Error("Podaj `slug` ucznia lub listę `uczniowie` (np. slug: ola).");
    }
    this._config = { ...config, widok };
    this._resetTygodnia();
    this._podpis = [];
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    const podpis = this._podpisStanow();
    const zmiana = podpis.length !== this._podpis.length || podpis.some((s, i) => s !== this._podpis[i]);
    if (zmiana) {
      this._podpis = podpis;
      this._render();
    }
  }
  get hass() {
    return this._hass;
  }

  getCardSize() {
    switch (this._config?.widok) {
      case "dzis":
      case "jutro":
        return 6;
      case "tydzien":
        return 9;
      default:
        return 4;
    }
  }

  connectedCallback() {
    // co minutę odświeżamy widok "dzis" (wyróżnienie aktualnej lekcji)
    if (!this._zegar && typeof setInterval === "function") {
      this._zegar = setInterval(() => {
        if (this._config?.widok === "dzis") this._render();
      }, 60000);
    }
    this._render();
  }

  disconnectedCallback() {
    if (this._zegar) clearInterval(this._zegar);
    this._zegar = null;
  }

  /* ---- stan ---- */

  _resetTygodnia() {
    this._zadanieNr = (this._zadanieNr || 0) + 1;
    this._tydzien = { dane: null, ladowanie: false, blad: null };
    this._wybor = null;
  }

  _teraz() {
    return new Date();
  }

  _uczniowie() {
    return wybierzUcznia(this._config, this._wybranySlug);
  }

  _podpisStanow() {
    if (!this._hass || !this._config) return [];
    const { wybrany } = this._uczniowie();
    if (!wybrany) return [];
    const st = this._hass.states || {};
    const ids = Object.values(entityIds(wybrany.slug));
    if (wybrany.numerek) ids.push(wybrany.numerek);
    return ids.map((id) => st[id]);
  }

  _stan(id) {
    return this._hass?.states?.[id] || null;
  }

  /* ---- zdarzenia ---- */

  _klik(e) {
    const el = e.target?.closest?.("[data-akcja]");
    if (!el || el.disabled) return;
    const akcja = el.dataset.akcja;
    if (akcja === "uczen") {
      const slug = el.dataset.slug;
      if (slug && slug !== this._uczniowie().wybrany?.slug) {
        this._wybranySlug = slug;
        zapiszUcznia(slug);
        this._resetTygodnia();
        this._otwarte.clear();
        this._podpis = this._podpisStanow();
        this._render();
      }
    } else if (akcja === "tydz-prev" || akcja === "tydz-next") {
      const pon = this._aktualnyPoniedzialek();
      if (pon) this._idzDoTygodnia(przesunTydzien(pon, akcja === "tydz-prev" ? -1 : 1));
    } else if (akcja === "tydz-teraz") {
      this._resetTygodnia();
      this._render();
    } else if (akcja === "tydz-dzien") {
      const i = Number(el.dataset.i);
      this._wybor = this._wybor?.typ === "dzien" && this._wybor.i === i ? null : { typ: "dzien", i };
      this._render();
    } else if (akcja === "tydz-komorka") {
      const i = Number(el.dataset.i);
      const n = Number(el.dataset.n);
      const ten = this._wybor?.typ === "komorka" && this._wybor.i === i && this._wybor.n === n;
      this._wybor = ten ? null : { typ: "komorka", i, n };
      this._render();
    } else if (akcja === "zamknij-panel") {
      this._wybor = null;
      this._render();
    }
  }

  _atrybutyTygodnia() {
    const { wybrany } = this._uczniowie();
    return wybrany ? this._stan(entityIds(wybrany.slug).plan_tygodnia)?.attributes || null : null;
  }

  _aktualnyPoniedzialek() {
    const dane = this._tydzien.dane || this._atrybutyTygodnia();
    return dane?.tydzien_od ? poniedzialekTygodnia(dane.tydzien_od) : null;
  }

  async _idzDoTygodnia(pon) {
    const a = this._atrybutyTygodnia();
    if (!a || !pon) return;
    const okno = oknoTygodni(dataIso(this._teraz()));
    if (!wOknie(pon, okno)) return;
    // tydzień z sensora – bez wołania usługi
    if (a.tydzien_od && poniedzialekTygodnia(a.tydzien_od) === pon) {
      this._resetTygodnia();
      this._render();
      return;
    }
    if (!a.entry_id) {
      this._tydzien.blad = "brak entry_id w atrybutach sensora planu tygodnia";
      this._render();
      return;
    }
    const nr = ++this._zadanieNr;
    this._tydzien.ladowanie = true;
    this._tydzien.blad = null;
    this._render();
    try {
      const wynik = await this._hass.callWS({
        type: "call_service",
        domain: "librus_apix",
        service: "pobierz_tydzien",
        service_data: { entry_id: a.entry_id, poniedzialek: pon },
        return_response: true,
      });
      if (nr !== this._zadanieNr) return;
      const dane = wynik?.response ?? null;
      if (!dane || !Array.isArray(dane.dni)) throw new Error("nieprawidłowa odpowiedź usługi");
      this._tydzien.dane = dane;
      this._wybor = null;
      this._otwarte.clear();
    } catch (err) {
      if (nr !== this._zadanieNr) return;
      this._tydzien.blad = err?.message || String(err);
    }
    this._tydzien.ladowanie = false;
    this._render();
  }

  /* ---- render ---- */

  _render() {
    if (!this.shadowRoot || !this._config) return;
    let tresc;
    try {
      tresc = this._html();
    } catch (err) {
      tresc = komunikat(`Błąd karty: ${esc(err?.message || err)}`, "⚠️");
    }
    this.shadowRoot.innerHTML = `<style>${CSS}</style><div class="karta">${tresc}</div>`;
    // przywróć rozwinięte <details>
    for (const d of this.shadowRoot.querySelectorAll("details[data-klucz]")) {
      if (this._otwarte.has(d.dataset.klucz)) d.open = true;
    }
  }

  _html() {
    if (!this._hass) return komunikat("Wczytywanie…", "⏳");
    const { uczniowie, wybrany } = this._uczniowie();
    const ids = entityIds(wybrany.slug);
    const czesci = [this._pasekWersji(ids), this._gora(uczniowie, wybrany)];
    const widok = this._config.widok;
    if (widok === "dzis" || widok === "jutro") czesci.push(this._widokDnia(ids, widok));
    else if (widok === "tydzien") czesci.push(this._widokTygodnia(ids));
    else if (widok === "zadania") czesci.push(this._widokZadan(ids));
    else if (widok === "plecak") czesci.push(this._widokPlecaka(ids));
    return czesci.join("");
  }

  _pasekWersji(ids) {
    const wersjaInt = this._stan(ids.plan_tygodnia)?.attributes?.wersja_integracji;
    const wersjaKarty = globalThis.__LIBRUS_CARD_VERSION__ || CARD_VERSION;
    if (!czyInnaWersja(wersjaKarty, wersjaInt)) return "";
    return `<div class="pasek-wersji" title="karta ${esc(wersjaKarty)}, integracja ${esc(wersjaInt)}">
      🔄 Karta jest w starszej wersji – odśwież stronę (Ctrl+Shift+R)</div>`;
  }

  _gora(uczniowie, wybrany) {
    const czesci = [];
    if (uczniowie.length > 1) {
      for (const u of uczniowie) {
        czesci.push(
          `<button class="chip-ucznia" data-akcja="uczen" data-slug="${esc(u.slug)}" aria-pressed="${
            u.slug === wybrany.slug
          }">${esc(u.nazwa)}</button>`,
        );
      }
    }
    if (wybrany.numerek) {
      const st = this._stan(wybrany.numerek);
      const wartosc = st?.state;
      if (st && wartosc !== "unknown" && wartosc !== "unavailable" && wartosc !== "") {
        const traf =
          wybrany.numer_w_dzienniku !== null && Number(wartosc) === Number(wybrany.numer_w_dzienniku);
        czesci.push(
          `<span class="numerek ${traf ? "trafiony" : ""}" title="Szczęśliwy numerek">🍀 ${esc(wartosc)}${
            traf ? " – to Ty! 🎉" : ""
          }</span>`,
        );
      }
    }
    return czesci.length ? `<div class="gora">${czesci.join("")}</div>` : "";
  }

  /* ---- widok: dziś / jutro ---- */

  _widokDnia(ids, tryb) {
    const id = tryb === "dzis" ? ids.plan_dzis : ids.plan_jutro;
    const st = this._stan(id);
    if (!st) return brakEncji(id);
    const a = st.attributes || {};
    const teraz = this._teraz();
    const dzis = dataIso(teraz);
    const etykieta = tryb === "dzis" ? "Dzisiaj" : etykietaDnia(a, a.czy_jutro, dzis) || "Jutro";
    const przedmioty = this._config.przedmioty;
    const lekcje = sortujLekcje(a.lekcje);

    const naglowek = `<div class="naglowek"><div class="tytul">${esc(etykieta)}</div>
      <div class="podtytul">${esc(a.dzien || "")} ${esc(fmtData(a.data))}${
        st.state && st.state !== "Wolne" ? ` · ${esc(st.state)}` : ""
      }</div></div>`;
    const wyd = chipyWydarzen(a.wydarzenia_dnia);

    if (a.dzien_wolny || !lekcje.length) {
      return `${naglowek}${wyd}${komunikat(
        a.dzien_wolny ? "Dzień wolny od zajęć" : "Brak lekcji",
        "🎉",
        "duzy",
      )}`;
    }

    let status = "";
    let akt = null;
    if (tryb === "dzis") {
      akt = aktualnaLekcja(lekcje, teraz);
      const opis = (l) => `${stylPrzedmiotu(l.przedmiot, przedmioty).emoji} ${l.przedmiot}`;
      if (akt.stan === "trwa") {
        status = `Teraz: <b>${esc(opis(akt.lekcja))}</b> do ${esc(akt.lekcja.do)}${
          akt.nastepna ? ` · potem ${esc(opis(akt.nastepna))}` : ""
        }`;
      } else if (akt.stan === "przed" || akt.stan === "przerwa") {
        const l = akt.nastepna;
        status = `${akt.stan === "przerwa" ? "Przerwa · n" : "N"}astępna: <b>${esc(opis(l))}</b> o ${esc(l.od)}${
          l.sala ? ` · ${esc(opisSali(l.sala))}` : ""
        }`;
      } else if (akt.stan === "po") {
        const nast = this._stan(ids.nastepna_lekcja);
        status = "Koniec lekcji na dziś 🎒";
        if (nast && nast.state && nast.state !== "Koniec lekcji" && nast.state !== "unknown") {
          status += ` · następna: <b>${esc(nast.state)}</b>${
            nast.attributes?.od ? ` o ${esc(nast.attributes.od)}` : ""
          }`;
        }
      }
    }

    const mapaOkienek = new Map(okienka(lekcje).map((o) => [o.po, o]));
    const kafle = [];
    for (const g of grupujPoNumerze(lekcje)) {
      for (const l of g.lekcje) kafle.push(this._kafel(l, akt));
      const o = mapaOkienek.get(g.numer);
      if (o) kafle.push(`<div class="okienko-wiersz">${esc(opisOkienka(o))}</div>`);
    }
    return `${naglowek}${status ? `<div class="status">${status}</div>` : ""}${wyd}<div class="kafle">${kafle.join(
      "",
    )}</div>`;
  }

  _kafel(l, akt) {
    const s = stylPrzedmiotu(l.przedmiot, this._config.przedmioty);
    const teraz = akt && akt.lekcja === l;
    const nastepna = akt && !akt.lekcja && akt.nastepna === l;
    const klasy = ["kafel", l.odwolana && "odwolana", l.zastepstwo && "zastepstwo", teraz && "teraz", nastepna && "nastepna"]
      .filter(Boolean)
      .join(" ");
    const meta = [l.nauczyciel, l.sala ? opisSali(l.sala) : ""].filter(Boolean);
    const podteksty = [];
    if (l.zastepstwo && opisZmiany(l.zmiana)) podteksty.push(`⚠ ${opisZmiany(l.zmiana)}`);
    for (const z of l.zadania || []) {
      podteksty.push(`🏠 ${[z.kategoria, z.tresc].filter(Boolean).join(": ") || "zadanie"}`);
    }
    for (const w of l.wydarzenia || []) if (w) podteksty.push(`${w.ikona || "📌"} ${w.tytul}`);
    if (l.info) podteksty.push(`ℹ️ ${l.info}`);
    return `<div class="${klasy}" style="${styleKoloru(s)}">
      ${teraz ? '<span class="znacznik">teraz</span>' : nastepna ? '<span class="znacznik">następna</span>' : ""}
      <div class="kafel-num">${esc(l.numer)}</div>
      <div class="kafel-czas">${esc(l.od)}–${esc(l.do)}</div>
      <div class="kafel-glowny"><span class="emoji">${esc(s.emoji)}</span> ${esc(l.przedmiot)}</div>
      ${meta.length ? `<div class="kafel-meta">${meta.map(esc).join(" · ")}</div>` : ""}
      ${plakietki(l)}
      ${podteksty.map((p) => `<div class="podtekst">${esc(p)}</div>`).join("")}
    </div>`;
  }

  /* ---- widok: tydzień ---- */

  _widokTygodnia(ids) {
    const st = this._stan(ids.plan_tygodnia);
    if (!st) return brakEncji(ids.plan_tygodnia);
    const a = st.attributes || {};
    const { dane: pobrane, ladowanie, blad } = this._tydzien;
    const dane = pobrane || a;
    const dzis = dataIso(this._teraz());
    const okno = oknoTygodni(dzis);
    const pon = dane.tydzien_od ? poniedzialekTygodnia(dane.tydzien_od) : null;
    const prev = pon ? przesunTydzien(pon, -1) : null;
    const next = pon ? przesunTydzien(pon, 1) : null;
    const zakres = pobrane
      ? `${fmtData(pon)}–${fmtData(dodajDni(pon, 4))}`
      : st.state && st.state !== "unknown"
        ? st.state
        : `${fmtData(pon)}–${fmtData(dodajDni(pon, 4))}`;

    const nawigacja = `<div class="nawigacja">
      <button data-akcja="tydz-prev" title="Poprzedni tydzień" aria-label="Poprzedni tydzień" ${
        ladowanie || !wOknie(prev, okno) ? "disabled" : ""
      }>◀</button>
      <div class="zakres">${esc(zakres)}${ladowanie ? ' <span class="laduje">wczytuję…</span>' : ""}</div>
      <button data-akcja="tydz-teraz" title="Bieżący tydzień" ${!pobrane && !ladowanie ? "disabled" : ""}>Teraz</button>
      <button data-akcja="tydz-next" title="Następny tydzień" aria-label="Następny tydzień" ${
        ladowanie || !wOknie(next, okno) ? "disabled" : ""
      }>▶</button>
    </div>`;

    const bladHtml = blad ? `<div class="blad">⚠️ Nie udało się pobrać tygodnia: ${esc(blad)}</div>` : "";
    const nieakt = dane.nieaktualne
      ? '<div class="ostrzezenie">⏳ Dane mogą być nieaktualne (brak połączenia z Librusem).</div>'
      : "";

    const siatka = zbudujSiatke(dane.dni, dane.numery_lekcji);
    let tresc;
    if (!siatka.kolumny.length) {
      tresc = komunikat("Brak danych planu dla tego tygodnia.", "📭");
    } else if (!siatka.wiersze.length) {
      tresc = `${this._linieWydarzen(siatka)}${komunikat("Brak lekcji w tym tygodniu", "🎉", "duzy")}`;
    } else {
      tresc = this._siatkaHtml(siatka, dane, dzis) + this._listaDniHtml(siatka, dzis);
    }
    return `<div class="tydzien ${ladowanie ? "wczytywanie" : ""}">${nawigacja}${bladHtml}${nieakt}<div class="tresc-tygodnia">${tresc}</div></div>`;
  }

  _linieWydarzen(siatka) {
    const linie = [];
    for (const k of siatka.kolumny) {
      for (const w of k.dzien.wydarzenia_dnia || []) {
        if (!w) continue;
        linie.push(
          `<div><b>${esc(k.skrot)}:</b> ${esc(w.ikona || "📌")} ${esc(w.tytul)}${
            w.przedmiot ? ` <span class="drugorzedny">(${esc(w.przedmiot)})</span>` : ""
          }</div>`,
        );
      }
    }
    return linie.length ? `<div class="wydarzenia-linie">${linie.join("")}</div>` : "";
  }

  _siatkaHtml(siatka, dane, dzis) {
    const przedmioty = this._config.przedmioty;
    const godziny = dane.godziny || {};
    const glowa = siatka.kolumny
      .map((k) => {
        const klasy = [k.data === dzis && "dzis", k.dzien.dzien_wolny && "wolny"].filter(Boolean).join(" ");
        const tip = [k.dzien.dzien, k.dzien.zakres].filter(Boolean).join(" · ");
        return `<th class="${klasy}"><button class="dzien-btn" data-akcja="tydz-dzien" data-i="${esc(
          k.indeks,
        )}" title="${esc(tip)}">${esc(k.skrot)} <span>${esc(fmtData(k.data))}</span>${
          k.dzien.dzien_wolny ? " 🎉" : ""
        }</button></th>`;
      })
      .join("");
    const wiersze = siatka.wiersze
      .map((w) => {
        const godz = godziny[String(w.numer)] || (w.od && w.do ? `${w.od}–${w.do}` : "");
        const komorki = w.komorki
          .map((c, ci) => {
            const k = siatka.kolumny[ci];
            const klasy = [k.data === dzis && "dzis", c.okienko && "okienko"].filter(Boolean).join(" ");
            if (c.luka) return `<td class="${klasy}"${c.okienko ? ' title="okienko"' : ""}></td>`;
            const wybrana =
              this._wybor?.typ === "komorka" && this._wybor.i === k.indeks && this._wybor.n === w.numer;
            const mini = c.lekcje
              .map((l) => {
                const s = stylPrzedmiotu(l.przedmiot, przedmioty);
                return `<span class="mini ${l.odwolana ? "odwolana" : ""}" style="${styleKoloru(s)}" title="${esc(
                  l.przedmiot,
                )}${l.sala ? ` · ${esc(opisSali(l.sala))}` : ""}"><span class="emoji">${esc(s.emoji)}</span><span class="skrot">${esc(
                  skrotPrzedmiotu(l.przedmiot, 8),
                )}</span>${plakietki(l, true)}</span>`;
              })
              .join("");
            return `<td class="${klasy}"><button class="komorka ${wybrana ? "wybrana" : ""}" data-akcja="tydz-komorka" data-i="${esc(
              k.indeks,
            )}" data-n="${esc(w.numer)}">${mini}</button></td>`;
          })
          .join("");
        return `<tr><th class="nr"><div>${esc(w.numer)}</div><div class="godz">${esc(godz)}</div></th>${komorki}</tr>`;
      })
      .join("");
    return `<div class="siatka-wrap"><table class="siatka"><thead><tr><th class="rog"></th>${glowa}</tr></thead><tbody>${wiersze}</tbody></table>${this._linieWydarzen(
      siatka,
    )}${this._panelHtml(siatka)}</div>`;
  }

  _panelHtml(siatka) {
    const w = this._wybor;
    if (!w) return "";
    const k = siatka.kolumny.find((x) => x.indeks === w.i);
    if (!k) return "";
    const przedmioty = this._config.przedmioty;
    const d = k.dzien;
    const zamknij = '<button class="zamknij" data-akcja="zamknij-panel" title="Zamknij" aria-label="Zamknij">✕</button>';
    if (w.typ === "komorka") {
      const lekcje = (d.lekcje || []).filter((l) => l?.numer === w.n);
      if (!lekcje.length) return "";
      return `<div class="panel">${zamknij}<div class="sz-meta">${esc(d.dzien || k.skrot)} ${esc(
        fmtData(k.data),
      )}</div>${lekcje.map((l) => szczegolyLekcji(l, przedmioty)).join("")}</div>`;
    }
    const lekcje = sortujLekcje(d.lekcje);
    const tresc = lekcje.length
      ? lekcje.map((l) => szczegolyLekcji(l, przedmioty)).join("")
      : komunikat(d.dzien_wolny ? "Dzień wolny" : "Brak lekcji", "🎉");
    return `<div class="panel">${zamknij}<div class="sz-tyt"><b>${esc(d.dzien || k.skrot)}</b> ${esc(
      fmtData(k.data),
    )} <span class="drugorzedny">· ${esc(d.zakres || "")}</span></div>${chipyWydarzen(d.wydarzenia_dnia)}${tresc}</div>`;
  }

  _listaDniHtml(siatka, dzis) {
    const przedmioty = this._config.przedmioty;
    const karty = siatka.kolumny.map((k) => {
      const d = k.dzien;
      const lekcje = sortujLekcje(d.lekcje);
      const mapaOkienek = new Map(okienka(lekcje).map((o) => [o.po, o]));
      let wnetrze = "";
      if (d.dzien_wolny || !lekcje.length) {
        wnetrze = `<div class="wolne">🎉 ${d.dzien_wolny ? "Dzień wolny" : "Brak lekcji"}</div>`;
      } else {
        const elementy = [];
        lekcje.forEach((l, idx) => {
          const s = stylPrzedmiotu(l.przedmiot, przedmioty);
          const klucz = `${k.data || k.indeks}-${l.numer}-${idx}`;
          elementy.push(`<details data-klucz="${esc(klucz)}" style="${styleKoloru(s)}"><summary>
            <span class="nr">${esc(l.numer)}</span><span class="czas">${esc(l.od)}</span>
            <span class="nazwa ${l.odwolana ? "odwolana-tekst" : ""}">${esc(s.emoji)} ${esc(l.przedmiot)}</span>
            ${plakietki(l, true)}</summary>${szczegolyLekcji(l, przedmioty)}</details>`);
          const nast = lekcje[idx + 1];
          const o = mapaOkienek.get(l.numer);
          if (o && (!nast || nast.numer !== l.numer)) {
            elementy.push(`<div class="okienko-wiersz">${esc(opisOkienka(o))}</div>`);
          }
        });
        wnetrze = elementy.join("");
      }
      return `<section class="dzien-karta ${k.data === dzis ? "dzis" : ""}"><header><span>${esc(
        d.dzien || k.skrot,
      )} <span class="drugorzedny">${esc(fmtData(k.data))}</span></span><span class="drugorzedny">${esc(
        d.dzien_wolny ? "" : d.zakres || "",
      )}</span></header>${chipyWydarzen(d.wydarzenia_dnia)}${wnetrze}</section>`;
    });
    return `<div class="lista-dni">${karty.join("")}</div>`;
  }

  /* ---- widok: zadania ---- */

  _widokZadan(ids) {
    const st = this._stan(ids.zadania_otwarte);
    if (!st) return brakEncji(ids.zadania_otwarte);
    const a = st.attributes || {};
    const g = grupujZadania([...(a.zadania || []), ...(a.po_terminie || [])]);
    const przedmioty = this._config.przedmioty;
    const sekcje = [
      ["dzis", "🔴 Dziś"],
      ["jutro", "🟠 Jutro"],
      ["tydzien", "🟡 W tym tygodniu"],
      ["pozniej", "⚪ Później"],
    ];
    const aktywne = sekcje.filter(([k]) => g[k].length);
    const lacznie = aktywne.reduce((s, [k]) => s + g[k].length, 0);
    let html = `<div class="naglowek"><div class="tytul">📚 Do odrobienia</div>${
      lacznie ? `<div class="podtytul">${esc(lacznie)} otwartych</div>` : ""
    }</div>`;
    if (!lacznie) html += komunikat("Nic do odrobienia 🎉", "✅", "duzy");
    for (const [k, tytul] of aktywne) {
      html += `<div class="sekcja"><h3>${esc(tytul)} (${esc(g[k].length)})</h3><ul class="zadania">${g[k]
        .map((z) => pozycjaZadania(z, przedmioty))
        .join("")}</ul></div>`;
    }
    if (g.po_terminie.length) {
      html += `<details class="po-terminie" data-klucz="po-terminie"><summary>Po terminie (${esc(
        g.po_terminie.length,
      )})</summary><ul class="zadania">${g.po_terminie.map((z) => pozycjaZadania(z, przedmioty)).join("")}</ul></details>`;
    }
    return html;
  }

  /* ---- widok: plecak ---- */

  _widokPlecaka(ids) {
    const st = this._stan(ids.do_zrobienia_jutro);
    if (!st) return brakEncji(ids.do_zrobienia_jutro);
    const a = st.attributes || {};
    const przedmioty = this._config.przedmioty;
    const dzis = dataIso(this._teraz());
    const etykieta = etykietaDnia({ data: a.data, dzien: a.dzien }, undefined, dzis) || "Jutro";
    const doSpakowania = Array.isArray(a.przedmioty_do_spakowania) ? a.przedmioty_do_spakowania : [];
    const zadania = Array.isArray(a.zadania) ? a.zadania : [];
    const sprawdziany = Array.isArray(a.sprawdziany) ? a.sprawdziany : [];

    let html = `<div class="naglowek"><div class="tytul">🎒 Spakuj plecak</div><div class="podtytul">${esc(
      etykieta,
    )}${a.dzien && etykieta === "Jutro" ? ` · ${esc(a.dzien)}` : ""} ${esc(fmtData(a.data))}</div></div>`;
    if (!doSpakowania.length && !zadania.length && !sprawdziany.length) {
      return html + komunikat("Nic na jutro 🎉", "😎", "duzy");
    }
    if (doSpakowania.length) {
      html += `<div class="sekcja"><h3>Przedmioty (${esc(doSpakowania.length)})</h3><div class="przedmioty-plecak">${doSpakowania
        .map((p) => {
          const s = stylPrzedmiotu(p, przedmioty);
          return `<div class="przedmiot-kafel" style="${styleKoloru(s)}"><span class="emoji">${esc(
            s.emoji,
          )}</span><span>${esc(p)}</span></div>`;
        })
        .join("")}</div></div>`;
    }
    if (sprawdziany.length) {
      html += `<div class="sekcja"><h3>📝 Sprawdziany i kartkówki</h3><ul class="lista-prosta">${sprawdziany
        .map(
          (s) =>
            `<li>${esc(s.ikona || "📝")} ${esc(s.tytul)}${s.przedmiot ? ` <span class="drugorzedny">· ${esc(s.przedmiot)}</span>` : ""}</li>`,
        )
        .join("")}</ul></div>`;
    }
    if (zadania.length) {
      html += `<div class="sekcja"><h3>🏠 Zadania na ${esc(etykieta === "Jutro" ? "jutro" : a.dzien || "")}</h3><ul class="zadania">${zadania
        .map((z) => pozycjaZadania(z, przedmioty))
        .join("")}</ul></div>`;
    }
    return html;
  }
}

if (typeof customElements !== "undefined" && !customElements.get("librus-card")) {
  customElements.define("librus-card", LibrusCard);
  globalThis.customCards = globalThis.customCards || [];
  if (!globalThis.customCards.some((c) => c.type === "librus-card")) {
    globalThis.customCards.push({
      type: "librus-card",
      name: "Librus – plan i zadania",
      description: "Plan lekcji (dziś, jutro, tydzień), zadania domowe i plecak na jutro z integracji Librus Synergia.",
      preview: false,
    });
  }
  console.info(`%c LIBRUS-CARD %c ${CARD_VERSION} `, "background:#1565c0;color:#fff", "");
}
