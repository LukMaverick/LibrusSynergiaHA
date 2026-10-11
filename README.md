# 🎓 Librus APIX Integration for Home Assistant

[![Buy Me A Coffee](https://img.shields.io/badge/Buy%20Me%20A%20Coffee-ffdd00?style=for-the-badge&logo=buy-me-a-coffee&logoColor=black)](https://buymeacoffee.com/LukMaverick)

Integracja Home Assistant z systemem Librus Synergia, umożliwiająca monitorowanie ocen, wiadomości i innych danych szkolnych.

## ✨ Funkcje

- 📊 **Monitoring ocen** - wszystkie oceny ze wszystkich przedmiotów
- 📈 **Statystyki** - średnie ocen, liczba ocen, trend
- 📧 **Wiadomości** - najnowsze wiadomości z dziennika
- 🔔 **Powiadomienia** - automatyczne powiadomienia o nowych ocenach/wiadomościach
- 📅 **Plan lekcji** - plan na dziś i jutro, widok tygodnia ze sprawdzianami, zadaniami i zastępstwami
- 🏠 **Dashboard dla dzieci** - własna karta `custom:librus-card` (wbudowana w integrację)

## 🚀 Sensory

Integracja tworzy następujące sensory:

| Sensor | Opis | Wartość |
|--------|------|---------|
| `sensor.informacje_o_uczniu` | Informacje o uczniu (klasa, wychowawca, szkoła) | imię i nazwisko |
| `sensor.szczesliwy_numerek` | Szczęśliwy numerek dnia | numer |
| `sensor.oceny` | Wszystkie oceny bieżącego semestru | liczba ocen |
| `sensor.srednia_ocen` | **Globalna średnia** ze wszystkich przedmiotów | float (wykres 📈) |
| `sensor.wiadomosci` | Ostatnie wiadomości (temat i nadawca) | liczba nieprzeczytanych |
| `sensor.terminarz` | Nadchodzące zdarzenia z terminarza | liczba zdarzeń |
| `sensor.zadania` | Zadania domowe (bez przeterminowanych) | liczba zadań |
| `sensor.<przedmiot>` | Oceny z danego przedmiotu (np. `sensor.matematyka`) | lista ocen: "4, 3+, 5" |
| `sensor.srednia_<przedmiot>` | **Średnia** z danego przedmiotu (np. `sensor.srednia_matematyka`) | float (wykres 📈) |

> Identyfikatory powstają z nazw encji. Jeśli Twoje wyglądają inaczej, sprawdź je w **Narzędzia deweloperskie → Stany**.

### 📅 Plan lekcji i zadania (od v1.3.0)

Te sensory mają stałe, przewidywalne identyfikatory: `sensor.librus_<imię>_...`, gdzie `<imię>` to imię ucznia (np. `ola`). Dla drugiego dziecka (osobny wpis integracji) wystarczy zmienić imię.

| Sensor | Stan | Najważniejsze atrybuty |
|--------|------|------------------------|
| `sensor.librus_<imię>_plan_dzis` | zakres godzin ("08:00–14:30") albo "Wolne" | `lekcje`, `przedmioty`, `liczba_sprawdzianow`, `wydarzenia_dnia`, `dzien_wolny` |
| `sensor.librus_<imię>_plan_jutro` | jak wyżej, dla najbliższego dnia nauki (w piątek poniedziałek) | j.w. oraz `data`, `dzien`, `czy_jutro` |
| `sensor.librus_<imię>_nastepna_lekcja` | przedmiot trwającej lub najbliższej lekcji, "Koniec lekcji", "Brak lekcji" | `od`, `do`, `sala`, `nauczyciel`, `trwa`, `sprawdzian` |
| `sensor.librus_<imię>_plan_tygodnia` | zakres dat ("12.10–18.10") | `dni`, `numery_lekcji`, `godziny`, `entry_id` |
| `sensor.librus_<imię>_do_zrobienia_jutro` | liczba zadań i sprawdzianów | `zadania`, `sprawdziany`, `przedmioty_do_spakowania`, `data` |
| `sensor.librus_<imię>_zadania_otwarte` | liczba zadań od dziś | `zadania` (z `pilnosc`, `tresc`), `liczba_dzis`, `liczba_jutro`, `po_terminie` |

`plan_tygodnia` domyślnie pokazuje najbliższy tydzień nauki: w sobotę, niedzielę i w piątek po ostatniej lekcji jest to **następny** tydzień, więc dziecko może przygotować się na cały tydzień. Plan jest scalony z terminarzem i zadaniami: lekcje mają znaczniki 📝 sprawdzian, 🏠 zadanie, ⚠ zastępstwo i ❌ odwołanie, a wycieczki, rady i dni wolne trafiają do `wydarzenia_dnia`.

Sensory średnich mają `state_class: measurement` — HA automatycznie rysuje dla nich wykres historyczny po kliknięciu w encję.

## 🧒 Karta `librus-card` – dashboard dla dzieci

Razem z integracją instaluje się własna karta Lovelace (bez dodatkowej instalacji z HACS). Integracja sama dodaje ją do zasobów dashboardów (tryb *storage*); po aktualizacji odśwież stronę (Ctrl+Shift+R). W trybie YAML karta ładuje się automatycznie przez `add_extra_js_url`. Jeśli wolisz zasób ręcznie: `url: /librus_apix_static/librus-card.js`, `type: module`.

Karta ma pięć widoków (`widok:`): `dzis`, `jutro`, `tydzien`, `zadania` (do odrobienia, z kolorami pilności) i `plecak` (przedmioty do spakowania + zadania i sprawdziany na jutro). Tydzień ma strzałki ◀ Teraz ▶ (od 2 tygodni wstecz do 4 w przód) i pokazuje cały nadchodzący tydzień w weekend.

```yaml
type: custom:librus-card
widok: tydzien
slug: ola              # imię ucznia z identyfikatorów sensor.librus_ola_*
```

Kilkoro dzieci w jednej karcie (chipy z przełącznikiem, wybór jest zapamiętany na urządzeniu):

```yaml
type: custom:librus-card
widok: dzis
uczniowie:
  - slug: ola
    nazwa: Ola
    numerek: sensor.szczesliwy_numerek   # opcjonalnie
    numer_w_dzienniku: 7                  # opcjonalnie: podświetla szczęśliwy numerek
  - slug: tomek
przedmioty:                               # opcjonalne nadpisania wyglądu
  Matematyka: { emoji: "🔢", kolor: "210 70% 55%" }
```

Podgląd karty bez Home Assistanta: uruchom `python3 -m http.server` w katalogu repo i otwórz `/custom_components/librus_apix/frontend/demo.html`.

### Usługa `librus_apix.pobierz_tydzien`

Karta używa jej do przełączania tygodni; możesz jej też użyć w automatyzacjach (`entry_id` jest atrybutem sensora `plan_tygodnia`). Zwraca plan tygodnia scalony z terminarzem i zadaniami. Bieżący i następny tydzień pochodzą z danych integracji, pozostałe są pobierane z Librusa i trzymane w pamięci przez godzinę.

### Plan awaryjny bez karty (markdown)

```yaml
type: markdown
content: >
  {% set s = 'sensor.librus_ola_plan_tygodnia' %}
  {% set dni = state_attr(s, 'dni') or [] %}
  ### 📅 {{ states(s) }}
  | Nr |{% for d in dni[:5] %} {{ d.skrot }} {{ d.data[8:] }}.{{ d.data[5:7] }}{{ ' 🎉' if d.dzien_wolny }} |{% endfor %}
  |---|{% for d in dni[:5] %}---|{% endfor %}
  {% for n in state_attr(s, 'numery_lekcji') or [] -%}
  | **{{ n }}** |{% for d in dni[:5] -%}
  {%- set l = d.lekcje | selectattr('numer', 'eq', n) | list | first | default(none) -%}
  {%- if l %} {{ '~~' if l.odwolana }}{{ l.przedmiot[:12] }}{{ '~~ ❌' if l.odwolana }}{{ ' ⚠' if l.zastepstwo }}{{ ' 📝' if l.sprawdzian }}{{ ' 🏠' if l.zadania }}{% endif %} |
  {%- endfor %}
  {% endfor %}
```

### Prywatność

`visible: - user: <id dziecka>` w widoku dashboardu ukrywa tylko zakładkę i **nie jest kontrolą dostępu**: konto dziecka mające dostęp do HA może odczytać wszystkie encje (także wiadomości) przez narzędzia deweloperskie lub API. Nie umieszczaj wiadomości na dashboardzie dziecka, a jeśli to ważne, ogranicz uprawnienia konta dziecka.

### Automatyzacje: plecak i zmiany w planie

```yaml
automation:
  - alias: "Librus: spakuj się na jutro"
    trigger:
      - platform: time
        at: "19:00:00"
    condition:
      - condition: template
        value_template: "{{ states('sensor.librus_ola_plan_jutro') != 'Wolne' }}"
    action:
      - service: notify.mobile_app_telefon_oli
        data:
          title: "Plecak na jutro 🎒"
          message: >
            {% set d = 'sensor.librus_ola_do_zrobienia_jutro' %}
            Przedmioty: {{ state_attr(d, 'przedmioty_do_spakowania') | join(', ') }}.
            {% for z in state_attr(d, 'zadania') %}
            🏠 {{ z.przedmiot }}{{ ': ' ~ z.tresc if z.tresc }}
            {% endfor %}
            {% for s in state_attr(d, 'sprawdziany') %}
            📝 {{ s.tytul }} {{ s.przedmiot }}
            {% endfor %}
```

Zdarzenie `librus_apix_nowe_zadanie` zawiera teraz także `id`, `termin_iso`, `dni_do`, `pilnosc`, `tresc` i `dzien_tygodnia_terminu` (dotychczasowe pola bez zmian).

## 📦 Instalacja

### Opcja 1: HACS (Zalecana)

Kliknij poniższy przycisk, aby automatycznie dodać repozytorium do HACS z właściwą kategorią:

[![Otwórz w HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=LukMaverick&repository=LibrusSynergiaHA&category=integration)

Lub ręcznie:

1. Otwórz HACS w Home Assistant
2. Kliknij trzy kropki (⋮) w prawym górnym rogu
3. Wybierz **"Custom repositories"**
4. W polu URL wpisz dokładnie: `https://github.com/LukMaverick/LibrusSynergiaHA`  
   ⚠️ **Bez `.git` na końcu!**
5. W polu **Category** wybierz: **`Integration`**  
   ⚠️ **NIE wybieraj "AppDaemon", "Plugin" ani żadnej innej opcji!**
6. Kliknij **ADD**
7. Znajdź **"Librus Synergia HA"** na liście i zainstaluj
8. Restartuj Home Assistant

> **Uwaga:** Błąd *"is not a valid app repository"* pojawia się, gdy w kroku 5 zostanie wybrana nieprawidłowa kategoria (np. "AppDaemon"). Upewnij się, że wybrano **Integration**.

### Opcja 2: Instalacja manualna

1. Skopiuj folder `custom_components/librus_apix` do `config/custom_components/`
2. Restartuj Home Assistant
3. Idź do Konfiguracja > Integracje > Dodaj integrację
4. Wyszukaj "Librus APIX"

## ⚙️ Konfiguracja

1. W Home Assistant: **Konfiguracja** > **Integracje** > **Dodaj integrację**
2. Wyszukaj **"Librus APIX"**  
3. Podaj swoje dane logowania do Librus Synergia:
   - **Login/Username**: Twój login do Librus
   - **Hasło**: Twoje hasło do Librus
4. Kliknij **"Prześlij"**

## 🔧 Środowisko testowe

Projekt zawiera local środowisko testowe z Docker:

```bash
# Uruchom środowisko testowe
docker-compose up -d

# Home Assistant dostępny pod: http://localhost:8123
# Code Server dostępny pod: http://localhost:8443 (hasło: homeassistant)
```

## 📊 Przykładowe karty Lovelace

### Karta ocen i średnich
```yaml
type: entities
title: "📚 Oceny Librus"
entities:
  - entity: sensor.srednia_ocen
    name: "Globalna średnia"
  - entity: sensor.oceny
    name: "Liczba ocen"
  - entity: sensor.szczesliwy_numerek
    name: "Szczęśliwy numerek"
```

### Karta wiadomości (Mushroom)

> **Wymagane:** [Mushroom Cards](https://github.com/piitaya/lovelace-mushroom) zainstalowane przez HACS.

#### Jak znaleźć nazwę swojej encji?
1. Idź do **Developer Tools → States**
2. Wyszukaj `wiadomosci`
3. Skopiuj pełną nazwę encji (np. `sensor.wiadomosci`)
4. Zamień `sensor.wiadomosci` poniżej na swoją nazwę

```yaml
type: vertical-stack
cards:
  - type: custom:mushroom-title-card
    title: 📬 Wiadomości Librus
    subtitle: >
      {% set n = state_attr('sensor.wiadomosci', 'liczba_nieprzeczytanych') %}
      {% if n > 0 %}{{ n }} nieprzeczytanych{% else %}Wszystkie przeczytane{% endif %}

  - type: custom:mushroom-template-card
    primary: >
      {{ state_attr('sensor.wiadomosci', 'wiadomosci')[0].temat | default('brak') }}
    secondary: >
      {{ state_attr('sensor.wiadomosci', 'wiadomosci')[0].nadawca | default('') }}
      · {{ state_attr('sensor.wiadomosci', 'wiadomosci')[0].data | default('') }}
    icon: mdi:message-text
    icon_color: >
      {% if state_attr('sensor.wiadomosci', 'wiadomosci')[0].nieprzeczytana %}red{% else %}grey{% endif %}
    badge_icon: >
      {% if state_attr('sensor.wiadomosci', 'wiadomosci')[0].ma_zalacznik %}mdi:paperclip{% endif %}

  - type: custom:mushroom-template-card
    primary: >
      {{ state_attr('sensor.wiadomosci', 'wiadomosci')[1].temat | default('brak') }}
    secondary: >
      {{ state_attr('sensor.wiadomosci', 'wiadomosci')[1].nadawca | default('') }}
      · {{ state_attr('sensor.wiadomosci', 'wiadomosci')[1].data | default('') }}
    icon: mdi:message-text
    icon_color: >
      {% if state_attr('sensor.wiadomosci', 'wiadomosci')[1].nieprzeczytana %}red{% else %}grey{% endif %}
    badge_icon: >
      {% if state_attr('sensor.wiadomosci', 'wiadomosci')[1].ma_zalacznik %}mdi:paperclip{% endif %}

  - type: custom:mushroom-template-card
    primary: >
      {{ state_attr('sensor.wiadomosci', 'wiadomosci')[2].temat | default('brak') }}
    secondary: >
      {{ state_attr('sensor.wiadomosci', 'wiadomosci')[2].nadawca | default('') }}
      · {{ state_attr('sensor.wiadomosci', 'wiadomosci')[2].data | default('') }}
    icon: mdi:message-text
    icon_color: >
      {% if state_attr('sensor.wiadomosci', 'wiadomosci')[2].nieprzeczytana %}red{% else %}grey{% endif %}
    badge_icon: >
      {% if state_attr('sensor.wiadomosci', 'wiadomosci')[2].ma_zalacznik %}mdi:paperclip{% endif %}

  - type: custom:mushroom-template-card
    primary: >
      {{ state_attr('sensor.wiadomosci', 'wiadomosci')[3].temat | default('brak') }}
    secondary: >
      {{ state_attr('sensor.wiadomosci', 'wiadomosci')[3].nadawca | default('') }}
      · {{ state_attr('sensor.wiadomosci', 'wiadomosci')[3].data | default('') }}
    icon: mdi:message-text
    icon_color: >
      {% if state_attr('sensor.wiadomosci', 'wiadomosci')[3].nieprzeczytana %}red{% else %}grey{% endif %}
    badge_icon: >
      {% if state_attr('sensor.wiadomosci', 'wiadomosci')[3].ma_zalacznik %}mdi:paperclip{% endif %}

  - type: custom:mushroom-template-card
    primary: >
      {{ state_attr('sensor.wiadomosci', 'wiadomosci')[4].temat | default('brak') }}
    secondary: >
      {{ state_attr('sensor.wiadomosci', 'wiadomosci')[4].nadawca | default('') }}
      · {{ state_attr('sensor.wiadomosci', 'wiadomosci')[4].data | default('') }}
    icon: mdi:message-text
    icon_color: >
      {% if state_attr('sensor.wiadomosci', 'wiadomosci')[4].nieprzeczytana %}red{% else %}grey{% endif %}
    badge_icon: >
      {% if state_attr('sensor.wiadomosci', 'wiadomosci')[4].ma_zalacznik %}mdi:paperclip{% endif %}
```

Legenda ikon:
- 🔴 czerwona = nieprzeczytana
- ⚫ szara = przeczytana
- 📎 badge = ma załącznik

### Karta terminarza (wszystkie zdarzenia)

> Znajdź nazwę encji w **Developer Tools → States** (szukaj `terminarz`).

```yaml
type: markdown
title: 📅 Terminarz
content: >
  {% set zdarzenia = state_attr('sensor.terminarz',
  'zdarzenia') %} {% if zdarzenia %} | Data | Dzień | Typ | Przedmiot | Opis |
   |------|-------|-----|-----------|------|
  {% for z in zdarzenia %} | **{{ z.data }}** | {{ z.tydzien }} | {{ z.tytul }}
  | {{ z.przedmiot }} | {{ z.szczegoly.Opis if z.szczegoly.Opis != 'unknown'
  else '' }} |

  {% endfor %} {% else %} Brak nadchodzących zdarzeń. {% endif %}
```

### Karta sprawdzianów i klasówek (bez dni wolnych)

```yaml
type: markdown
title: 📝 Sprawdziany i klasówki
content: >
  {% set zdarzenia = state_attr('sensor.terminarz',
  'zdarzenia') %} {% set typy_testow = ['Sprawdzian', 'Kartkówka', 'Klasówka',
  'Praca klasowa'] %} {% set sprawdziany = zdarzenia | selectattr('tytul', 'in',
  typy_testow) | list %} {% if sprawdziany %} | Data | Dzień | Typ | Przedmiot |
  Opis |
   |------|-------|-----|-----------|------|
  {% for z in sprawdziany %} | **{{ z.data }}** | {{ z.tydzien }} | {{ z.tytul
  }} | {{ z.przedmiot }} | {{ z.szczegoly.Opis if z.szczegoly.Opis != 'unknown'
  else '' }} |

  {% endfor %} {% else %} Brak nadchodzących zdarzeń. {% endif %}
```

### Wykres średniej z przedmiotu (Gauge)
```yaml
type: gauge
entity: sensor.srednia_matematyka
name: "Matematyka - średnia"
min: 1
max: 6
severity:
  green: 4.5
  yellow: 3
  red: 0
```

## 🔔 Automatyzacje powiadomień na telefon

Integracja wysyła zdarzenia Home Assistant gdy pojawi się nowa wiadomość lub ocena.
Zdarzenia są wykrywane przy każdym odświeżeniu (co 2h). Pierwsze uruchomienie tylko zapamiętuje stan — **nie wysyła duplikatów**.

> **Test bez czekania:** Idź do **Developer Tools → Events**, Event type: `librus_apix_nowa_wiadomosc`, Event data jak poniżej i kliknij **Fire Event**.

### 📬 Powiadomienie o nowej wiadomości

Zdarzenie: `librus_apix_nowa_wiadomosc`  
Dostępne dane: `nadawca`, `temat`, `data`, `ma_zalacznik`

> **Uwaga:** Treść wiadomości nie jest pobierana celowo — aby nie oznaczać wiadomości jako przeczytanych w Librusie.

```yaml
automation:
  - alias: "Librus - nowa wiadomosc"
    trigger:
      - platform: event
        event_type: librus_apix_nowa_wiadomosc
    action:
      - service: notify.mobile_app_NAZWA_TWOJEGO_TELEFONU
        data:
          title: "📬 Librus: nowa wiadomość"
          message: >-
            {% set msg = state_attr('sensor.librus_IMIE_NAZWISKO_wiadomosci', 'wiadomosci')
               | selectattr('nieprzeczytana', 'equalto', true) | list | first | default({}) %}
            Od: {{ msg.nadawca | default('nieznany') }}
            Temat: {{ msg.temat | default('brak') }}
```

> **Uwaga:** Zamień `sensor.librus_IMIE_NAZWISKO_wiadomosci` na nazwę swojego sensora widoczną w Developer Tools → States.

### 📝 Powiadomienie o nowej ocenie

Zdarzenie: `librus_apix_nowa_ocena`  
Dostępne dane: `przedmiot`, `ocena`, `data`, `kategoria`, `nauczyciel`

```yaml
automation:
  - alias: "Librus - nowa ocena"
    trigger:
      platform: event
      event_type: librus_apix_nowa_ocena
    action:
      - service: notify.mobile_app_NAZWA_TWOJEGO_TELEFONU
        data:
          title: "🎓 Librus: nowa ocena {{ trigger.event.data.ocena }}"
          message: >-
            {{ trigger.event.data.przedmiot }}
            Ocena: {{ trigger.event.data.ocena }}
            Kategoria: {{ trigger.event.data.kategoria }}
            Nauczyciel: {{ trigger.event.data.nauczyciel }}
```

> **Gdzie znaleźć nazwę telefonu?** HA → Settings → Devices & Services → Mobile App → nazwa urządzenia (np. `notify.mobile_app_samsung_galaxy_s24`)

## 🛠️ Rozwój

### Wymagania
- Python 3.9+
- Home Assistant 2023.1+
- librus-apix library

### Setup środowiska deweloperskiego
```bash
# Klonuj repozytorium
git clone https://github.com/twoje-username/librus-ha-integration
cd librus-ha-integration

# Uruchom środowisko testowe
docker-compose up -d

# Edytuj kod w Code Server (http://localhost:8443)
```

### Uruchomienie testów
```bash
pytest tests/
```

## 📝 Logi

Aby włączyć szczegółowe logi, dodaj do `configuration.yaml`:

```yaml
logger:
  logs:
    custom_components.librus_apix: debug
```

## ⚠️ Bezpieczeństwo

- **Nie udostępniaj swoich danych logowania!**  
- Dane są przechowywane lokalnie w Home Assistant
- Komunikacja z Librus odbywa się przez bezpieczne API
- Hasła są zaszyfrowane w konfiguracji

## 🐛 Zgłaszanie błędów

Jeśli znajdziesz błąd:

1. Włącz logi debug (patrz wyżej)
2. Skopiuj logi z błędem
3. Utwórz issue na GitHub z:
   - Opisem problemu
   - Krokami do reprodukcji
   - Logami (usuń dane osobowe!)

## 📄 Licencja

MIT License - patrz [LICENSE](LICENSE)

## 🤝 Wkład

Pull requesty są mile widziane! Sprawdź [CONTRIBUTING.md](CONTRIBUTING.md)

### 🙏 Podziękowania

Specjalne podziękowania dla **KB** za wsparcie i pomoc w rozwoju projektu.

## 👨‍💻 Autor

Stworzono na bazie biblioteki [librus-apix](https://github.com/RustySnek/librus-apix)

---

**⭐ Jeśli podoba Ci się projekt, zostaw gwiazdkę na GitHub!**

## ☕ Wesprzyj projekt

Jeśli integracja jest dla Ciebie przydatna, możesz postawić kawę 😊

[![Buy Me A Coffee](https://img.shields.io/badge/Buy%20Me%20A%20Coffee-ffdd00?style=for-the-badge&logo=buy-me-a-coffee&logoColor=black)](https://buymeacoffee.com/LukMaverick)