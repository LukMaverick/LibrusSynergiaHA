# 🎓 Librus APIX Integration for Home Assistant

[![Buy Me A Coffee](https://img.shields.io/badge/Buy%20Me%20A%20Coffee-ffdd00?style=for-the-badge&logo=buy-me-a-coffee&logoColor=black)](https://buymeacoffee.com/LukMaverick)

Integracja Home Assistant z systemem Librus Synergia, umożliwiająca monitorowanie ocen, wiadomości i innych danych szkolnych.

## ✨ Funkcje

- 📊 **Monitoring ocen** - wszystkie oceny ze wszystkich przedmiotów
- 📈 **Statystyki** - średnie ocen, liczba ocen, trend
- 📧 **Wiadomości** - najnowsze wiadomości z dziennika
- 🗓️ **Plan lekcji** - bieżący i następny tydzień, z zastępstwami i odwołanymi lekcjami
- 🔔 **Powiadomienia** - automatyczne powiadomienia o nowych ocenach/wiadomościach
- 🏠 **Dashboard** - piękne karty w Home Assistant

## 🚀 Sensory

Integracja tworzy następujące sensory:

| Sensor | Opis | Wartość |
|--------|------|---------|
| `sensor.librus_uczen` | Informacje o uczniu (klasa, wychowawca, szkoła) | imię i nazwisko |
| `sensor.librus_szczesliwy_numerek` | Szczęśliwy numerek dnia | numer |
| `sensor.librus_oceny` | Wszystkie oceny bieżącego semestru | liczba ocen |
| `sensor.librus_srednia_ocen` | **Globalna średnia** ze wszystkich przedmiotów | float (wykres 📈) |
| `sensor.librus_wiadomosci` | Ostatnie 5 wiadomości z pełną treścią | liczba nieprzeczytanych |
| `sensor.librus_plan_lekcji` | Plan lekcji na bieżący i następny tydzień | liczba lekcji dzisiaj |
| `sensor.librus_nastepna_lekcja` | Trwająca lub najbliższa lekcja (odświeżana co minutę) | nazwa przedmiotu |
| `sensor.librus_<przedmiot>` | Oceny z danego przedmiotu (np. `sensor.librus_matematyka`) | lista ocen: "4, 3+, 5" |
| `sensor.librus_srednia_<przedmiot>` | **Średnia** z danego przedmiotu (np. `sensor.librus_srednia_matematyka`) | float (wykres 📈) |

Sensor `nastepna_lekcja` przelicza swój stan co minutę lokalnie — **bez dodatkowych zapytań do Librusa**
(dane planu pobierane są razem z resztą, co 2 godziny).

Sensory średnich mają `state_class: measurement` — HA automatycznie rysuje dla nich wykres historyczny po kliknięciu w encję.

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

### Częstotliwość odświeżania

**Ustawienia → Urządzenia i usługi → Librus APIX → Konfiguruj**

Domyślnie integracja odpytuje Librusa **co 2 godziny** (120 minut, zakres 15–1440).
Zmiana działa od razu — Home Assistant przeładowuje integrację po zapisaniu opcji,
restart nie jest potrzebny.

Jedno odświeżenie to **8 zapytań HTTP**: oceny, wiadomości, zadania domowe, dane
ucznia, terminarz (2 miesiące) i plan lekcji (2 tygodnie). Przy 120 minutach daje
to około 96 zapytań na dobę. Warto o tym pamiętać, schodząc do 15 minut — będzie
ich wtedy ponad 750.

> Czujniki `Plan lekcji` i `Następna lekcja` przeliczają się **co minutę lokalnie**,
> bez odpytywania Librusa. Dlatego odliczanie „za X minut" i przeskok na kolejny
> dzień działają na bieżąco niezależnie od tego, jak rzadko pobierane są dane.

Po dodaniu integracji encje pojawią się w ciągu kilku sekund. Gotowy dashboard
z planem lekcji wklejasz z pliku
**[`examples/dashboard-plan-lekcji.yaml`](examples/dashboard-plan-lekcji.yaml)** —
instrukcja krok po kroku w sekcji
[Gotowy dashboard](#-gotowy-dashboard--plik-do-wklejenia).

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
  - entity: sensor.librus_srednia_ocen
    name: "Globalna średnia"
  - entity: sensor.librus_oceny
    name: "Liczba ocen"
  - entity: sensor.librus_szczesliwy_numerek
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

### 🚀 Gotowy dashboard — plik do wklejenia

Nie musisz składać kart ręcznie. W repozytorium jest kompletny dashboard
z planem lekcji:

**[`examples/dashboard-plan-lekcji.yaml`](examples/dashboard-plan-lekcji.yaml)**

Zawiera trzy karty jedna pod drugą: **Nadchodzące wydarzenia → Plan lekcji →
Plan tygodnia**.

#### Jak go wdrożyć

1. **Zainstaluj Mushroom Cards** — HACS → Frontend → wyszukaj `Mushroom`.
   Bez tego karty `custom:mushroom-*` pokażą *„Custom element doesn't exist"*.
2. **Sprawdź nazwę swojej encji** — Narzędzia deweloperskie → Stany, wpisz
   `plan_lekcji`. Encje biorą nazwę od imienia i nazwiska ucznia, np.
   `sensor.librus_jan_kowalski_plan_lekcji`.
3. **Utwórz dashboard** — Ustawienia → Dashboardy → Dodaj dashboard →
   Nowy dashboard od zera.
4. **Wklej konfigurację** — otwórz nowy dashboard, menu ⋮ → Edytuj, potem
   ponownie ⋮ → **Edytor nieprzetworzonej konfiguracji**. Wklej całą zawartość
   pliku.
5. **Podmień encję** — zamień w całym wklejonym tekście
   `sensor.librus_imie_nazwisko` na swoją nazwę z kroku 2. Zapisz.

> **Uwaga o układzie:** karty są opakowane w jeden `vertical-stack`, żeby
> wymusić jedną kolumnę. `max_columns: 1` **nie zadziała** — domyślny widok
> Lovelace (masonry) ma puste `setConfig()` i liczy kolumny wyłącznie
> z szerokości ekranu, ignorując konfigurację widoku.

Pojedyncze karty opisane są niżej — przydadzą się, jeśli chcesz je wpleść
we własny dashboard zamiast używać gotowego pliku.

### Karta nadchodzących wydarzeń (4 tygodnie)

> Korzysta z sensora `terminarz`, który pobiera bieżący i następny miesiąc.
> **4 tygodnie to maksimum, jakie ten sensor gwarantuje.** Najkrótszy możliwy
> horyzont wypada 31 stycznia (do 28 lutego) i wynosi dokładnie 28 dni — dłuższy
> okres po cichu urywałby się na końcu następnego miesiąca.

```yaml
type: vertical-stack
cards:
  - type: custom:mushroom-title-card
    title: 📅 Nadchodzące wydarzenia
    subtitle: >-
      {% set z = state_attr('sensor.librus_imie_nazwisko_terminarz', 'zdarzenia') or [] %}
      {% set do = (now() + timedelta(days=28)).strftime('%Y-%m-%d') %}
      {% set n = z | selectattr('data', 'le', do) | list | count %}
      {% set r = n % 10 %}{% set s = n % 100 %}
      {% if n == 0 %}Najbliższe 4 tygodnie bez wydarzeń{% else %}{{ n }}
      {% if n == 1 %}wydarzenie{% elif r in [2, 3, 4] and s not in [12, 13, 14] %}wydarzenia{% else %}wydarzeń{% endif %}
      w najbliższych 4 tygodniach{% endif %}

  - type: markdown
    content: |-
      {%- set wszystkie = state_attr('sensor.librus_imie_nazwisko_terminarz', 'zdarzenia') or [] %}
      {%- set do = (now() + timedelta(days=28)).strftime('%Y-%m-%d') %}
      {%- set zdarzenia = wszystkie | selectattr('data', 'le', do) | list %}
      {%- set testy = ['sprawdzian', 'kartkówka', 'klasówka', 'praca klasowa'] %}
      {%- if zdarzenia %}
      | Data | Dzień | Wydarzenie | Przedmiot | Szczegóły |
      |------|-------|------------|-----------|-----------|
      {%- for z in zdarzenia %}
      {%- set k = '#e53935' if z.tytul | lower in testy else '' %}
      {%- set opis = z.szczegoly.Opis if z.szczegoly.Opis not in [none, '', 'unknown'] else '' %}
      | {% if k %}<font color="{{ k }}">**{% endif %}{{ z.data }}{% if k %}**</font>{% endif %} | {% if k %}<font color="{{ k }}">**{% endif %}{{ z.tydzien }}{% if k %}**</font>{% endif %} | {% if k %}<font color="{{ k }}">**{% endif %}{{ z.tytul }}{% if k %}**</font>{% endif %} | {% if k %}<font color="{{ k }}">**{% endif %}{{ z.przedmiot }}{% if k %}**</font>{% endif %} | {{ opis }}{% if z.godzina not in ['', 'unknown', none] %}{% if opis %} · {% endif %}{{ z.godzina }}{% endif %} |
      {%- endfor %}
      {%- else %}
      Brak wydarzeń w najbliższych 4 tygodniach.
      {%- endif %}
```

Sprawdziany i kartkówki są <font color="#e53935">**czerwone i pogrubione**</font> —
tak samo jak w planie lekcji. Horyzont skrócisz podmieniając `days=28` — zwiększać nie ma sensu (patrz uwaga wyżej).

### Karta terminarza (wszystkie zdarzenia)

> Znajdź nazwę encji w **Developer Tools → States** (szukaj `terminarz`).

```yaml
type: markdown
title: 📅 Terminarz
content: >
  {% set zdarzenia = state_attr('sensor.librus_imie_nazwisko_terminarz',
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
  {% set zdarzenia = state_attr('sensor.librus_imie_nazwisko_terminarz',
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

### Karta planu lekcji (Mushroom)

> **Wymagane:** [Mushroom Cards](https://github.com/piitaya/lovelace-mushroom) zainstalowane przez HACS.
> Nazwy encji znajdziesz w **Developer Tools → States** (szukaj `plan_lekcji`).

```yaml
type: vertical-stack
cards:
  - type: custom:mushroom-title-card
    title: 📚 Plan lekcji
    subtitle: >-
      {% set p = 'sensor.librus_imie_nazwisko_plan_lekcji' %}
      {% set dt = state_attr(p, 'biezacy_dzien_data') %}
      {% set tydzien = state_attr(p, 'tydzien') %}
      {% set d = tydzien[dt] if dt in tydzien else [] %}
      {% if not d %}Brak nadchodzących lekcji 🎉{% else %}{% if
      dt == now().strftime('%Y-%m-%d') %}Dziś{% else
      %}{{ state_attr(p, 'biezacy_dzien_nazwa') }} {{ state_attr(p, 'biezacy_dzien_data')
      }}{% endif %} · {{ d | count }} lekcji · {{ d[0].od }}–{{ d[-1].do }}{% endif %}

  - type: custom:mushroom-template-card
    primary: >-
      {% set s = 'sensor.librus_imie_nazwisko_nastepna_lekcja' %}
      {% if states(s) in ['unknown', 'unavailable', 'None'] %}
        Brak zaplanowanych lekcji
      {% else %}
        {{ states(s) }}
      {% endif %}
    secondary: >-
      {% set s = 'sensor.librus_imie_nazwisko_nastepna_lekcja' %}
      {% if states(s) in ['unknown', 'unavailable', 'None'] %}
        —
      {% elif state_attr(s, 'trwa_teraz') %}
        Trwa do {{ state_attr(s, 'do') }} · {{ state_attr(s, 'nauczyciel_sala') }}
      {% elif state_attr(s, 'data') != now().strftime('%Y-%m-%d') %}
        {{ state_attr(s, 'dzien_tygodnia') }} {{ state_attr(s, 'od') }} · {{ state_attr(s, 'nauczyciel_sala') }}
      {% else %}
        {{ state_attr(s, 'numer') }}. lekcja · {{ state_attr(s, 'od') }} ·
        za {{ state_attr(s, 'za_minut') }} min
      {% endif %}
    icon: >-
      {% set s = 'sensor.librus_imie_nazwisko_nastepna_lekcja' %}
      {% if state_attr(s, 'trwa_teraz') %}mdi:school
      {% elif state_attr(s, 'data') != now().strftime('%Y-%m-%d') %}mdi:calendar-clock
      {% else %}mdi:clock-start{% endif %}
    icon_color: >-
      {% set s = 'sensor.librus_imie_nazwisko_nastepna_lekcja' %}
      {% if state_attr(s, 'zastepstwo') %}orange
      {% elif state_attr(s, 'trwa_teraz') %}green
      {% else %}blue{% endif %}
    badge_icon: >-
      {% if state_attr('sensor.librus_imie_nazwisko_nastepna_lekcja', 'zastepstwo') %}
        mdi:account-switch
      {% endif %}
    badge_color: orange

  - type: conditional
    conditions:
      - condition: state
        entity: sensor.librus_imie_nazwisko_plan_lekcji
        attribute: sa_zmiany
        state: true
    card:
      type: custom:mushroom-template-card
      primary: Zmiany w planie
      secondary: >-
        {% set z = state_attr('sensor.librus_imie_nazwisko_plan_lekcji', 'zmiany') %}
        {{ z | count }} zmian w najbliższym tygodniu
      icon: mdi:calendar-alert
      icon_color: orange

  - type: markdown
    content: |-
      {%- set p = 'sensor.librus_imie_nazwisko_plan_lekcji' %}
      {%- set d = state_attr(p, 'biezacy_dzien_data') %}
      {%- set tydzien = state_attr(p, 'tydzien') %}
      {%- set lekcje = tydzien[d] if d in tydzien else [] %}
      {%- set wd = state_attr(p, 'wydarzenia_dnia') %}
      {%- set zd = state_attr(p, 'zadania_dnia') %}
      {%- if lekcje %}
      **{{ state_attr(p, 'biezacy_dzien_nazwa') }}, {{ d }}**
      {%- for w in (wd[d] if d in wd else []) %}

      📌 {{ w.przedmiot }}{% if w.godzina not in ['', 'unknown'] %} · {{ w.godzina }}{% endif %}
      {%- endfor %}
      {%- for z in (zd[d] if d in zd else []) %}

      📚 {{ z.przedmiot }} · {{ z.kategoria }}
      {%- endfor %}

      | # | Godzina | Przedmiot | Sala |
      |---|---------|-----------|------|
      {%- for l in lekcje %}
      {%- set k = '#e53935' if l.wydarzenia else ('#f9a825' if l.zadania else '') %}
      | {% if k %}<font color="{{ k }}">**{% endif %}{{ l.numer }}{% if k %}**</font>{% endif %} | {% if k %}<font color="{{ k }}">**{% endif %}{{ l.od }}–{{ l.do }}{% if k %}**</font>{% endif %} | {% if k %}<font color="{{ k }}">**{% endif %}{% if l.odwolana %}~~{{ l.przedmiot }}~~{% elif l.zastepstwo and not k %}**{{ l.przedmiot }}** ⚠️{% elif l.zastepstwo %}{{ l.przedmiot }} ⚠️{% else %}{{ l.przedmiot }}{% endif %}{% for w in l.wydarzenia %} 📝 {{ w.tytul }}{% endfor %}{% for z in l.zadania %} 📚 {{ z.kategoria }}{% endfor %}{% if k %}**</font>{% endif %} | {% if k %}<font color="{{ k }}">**{% endif %}{{ l.nauczyciel_sala }}{% if k %}**</font>{% endif %} |
      {%- endfor %}
      {%- else %}
      Brak nadchodzących lekcji.
      {%- endif %}
```

Legenda:
- 🟢 zielona ikona = lekcja trwa teraz
- 🟠 pomarańczowa + 🔀 badge = zastępstwo
- ~~przekreślony~~ przedmiot = lekcja odwołana
- 📝 przy przedmiocie = wydarzenie z terminarza (sprawdzian, kartkówka)
- 📚 przy przedmiocie = praca domowa na ten dzień
- 📌 nad tabelą = wydarzenie całodniowe (wywiadówka, dzień wolny)
- <font color="#e53935">**czerwony pogrubiony wiersz**</font> = tego dnia jest sprawdzian/kartkówka z tego przedmiotu
- <font color="#f9a825">**żółty pogrubiony wiersz**</font> = na ten dzień jest praca domowa

> **Dlaczego kolor tekstu, a nie tło wiersza?** Karta markdown w Home Assistant
> przepuszcza treść przez sanitizer (biblioteka `xss`), który usuwa atrybuty
> `style`, `class` i `bgcolor` ze znaczników `<tr>` i `<td>`. Tła wiersza nie da się
> więc ustawić bez dodatkowych modułów z HACS. Znacznik `<font color>` jest na
> białej liście i działa bez żadnych instalacji.

### Karta planu na cały tydzień

```yaml
type: markdown
title: 🗓️ Plan tygodnia
content: |-
  {%- set p = 'sensor.librus_imie_nazwisko_plan_lekcji' %}
  {%- set tydzien = state_attr(p, 'tydzien') %}
  {%- set wd = state_attr(p, 'wydarzenia_dnia') %}
  {%- set zd = state_attr(p, 'zadania_dnia') %}
  {%- if tydzien %}
  {%- for data, lekcje in tydzien.items() %}
  **{{ lekcje[0].dzien_tygodnia }} {{ data }}**
  {%- for w in (wd[data] if data in wd else []) %}

  📌 {{ w.przedmiot }}{% if w.godzina not in ['', 'unknown'] %} · {{ w.godzina }}{% endif %}
  {%- endfor %}
  {%- for z in (zd[data] if data in zd else []) %}

  📚 {{ z.przedmiot }} · {{ z.kategoria }}
  {%- endfor %}

  | # | Godzina | Przedmiot | Sala |
  |---|---------|-----------|------|
  {%- for l in lekcje %}
  {%- set k = '#e53935' if l.wydarzenia else ('#f9a825' if l.zadania else '') %}
  | {% if k %}<font color="{{ k }}">**{% endif %}{{ l.numer }}{% if k %}**</font>{% endif %} | {% if k %}<font color="{{ k }}">**{% endif %}{{ l.od }}–{{ l.do }}{% if k %}**</font>{% endif %} | {% if k %}<font color="{{ k }}">**{% endif %}{% if l.odwolana %}~~{{ l.przedmiot }}~~{% elif l.zastepstwo and not k %}**{{ l.przedmiot }}** ⚠️{% elif l.zastepstwo %}{{ l.przedmiot }} ⚠️{% else %}{{ l.przedmiot }}{% endif %}{% for w in l.wydarzenia %} 📝 {{ w.tytul }}{% endfor %}{% for z in l.zadania %} 📚 {{ z.kategoria }}{% endfor %}{% if k %}**</font>{% endif %} | {% if k %}<font color="{{ k }}">**{% endif %}{{ l.nauczyciel_sala }}{% if k %}**</font>{% endif %} |
  {%- endfor %}
  {% endfor %}
  {%- else %}
  Brak danych o planie lekcji.
  {%- endif %}
```

**Dzień znika, gdy skończy się jego ostatnia lekcja.** Po ostatniej lekcji dnia karta
przechodzi na najbliższy kolejny dzień z zajęciami, a plan tygodnia przestaje pokazywać
dni już zakończone — i **dobiera kolejny dzień w jego miejsce**, więc widać zawsze 5 dni
lekcyjnych, a nie 4 po południu. Liczbę dni zmienisz stałą `DEFAULT_PLAN_DAYS`
w `const.py`. Tę samą zasadę stosuje atrybut `zmiany` — zastępstwo z lekcji,
która już się odbyła, nie jest raportowane.

Atrybut `tydzien` (słownik `data → lekcje`) zawiera **zawsze 5 najbliższych dni
lekcyjnych** i jest **jedynym miejscem z listą lekcji** — recorder w Home Assistant odrzuca stan encji powyżej 16 KB
atrybutów, więc lekcje nie są duplikowane. Dzień do wyświetlenia wskazują
`biezacy_dzien_data` i `biezacy_dzien_nazwa`; karta pobiera lekcje przez
`tydzien[biezacy_dzien_data]`. Czujnik przelicza to co minutę lokalnie, bez odpytywania
Librusa.

Każda lekcja ma pola `wydarzenia` (z terminarza) i `zadania` (prace domowe na ten dzień).
Czego nie dało się przypiąć do konkretnej lekcji, trafia do `wydarzenia_dnia`
i `zadania_dnia` (słowniki `data → lista`).

### Wykres średniej z przedmiotu (Gauge)
```yaml
type: gauge
entity: sensor.librus_srednia_matematyka
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

### 🔀 Powiadomienie o zastępstwie lub odwołanej lekcji

Zdarzenie: `librus_apix_zmiana_planu`
Dostępne dane: `data`, `dzien_tygodnia`, `numer`, `przedmiot`, `od`, `do`, `rodzaj` (`zastepstwo` / `odwolana`), `info`

```yaml
automation:
  - alias: "Librus - zmiana w planie lekcji"
    trigger:
      platform: event
      event_type: librus_apix_zmiana_planu
    action:
      - service: notify.mobile_app_NAZWA_TWOJEGO_TELEFONU
        data:
          title: >-
            {% if trigger.event.data.rodzaj == 'odwolana' %}
              🚫 Lekcja odwołana
            {% else %}
              🔀 Zastępstwo
            {% endif %}
          message: >-
            {{ trigger.event.data.dzien_tygodnia }} {{ trigger.event.data.data }},
            {{ trigger.event.data.numer }}. lekcja ({{ trigger.event.data.od }}):
            {{ trigger.event.data.przedmiot }}
```

> Pierwsze uruchomienie integracji tylko zapamiętuje bieżący stan planu — powiadomienia
> przychodzą dopiero o **nowo wykrytych** zmianach.

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

## 📄 Licencja i komponenty zewnętrzne

Projekt jest udostępniany na licencji **MIT** — pełny tekst w pliku
[LICENSE](LICENSE).

Poniższe składniki **nie są dystrybuowane razem z tym repozytorium** — Home
Assistant lub HACS pobierają je osobno. Wymieniamy je dla przejrzystości:

| Komponent | Licencja | Autor | Sposób użycia |
|-----------|----------|-------|----------------|
| [librus-apix](https://github.com/poroknights/librus-apix) | MIT | Pascal Jodłowski | zależność `pip`, deklarowana w `manifest.json` |
| [Mushroom Cards](https://github.com/piitaya/lovelace-mushroom) | Apache-2.0 | piitaya | opcjonalny dodatek frontendu, instalowany z HACS |
| [Home Assistant](https://github.com/home-assistant/core) | Apache-2.0 | Nabu Casa i społeczność | środowisko uruchomieniowe integracji |

Integracja komunikuje się z systemem **Librus Synergia**. Projekt nie jest
powiązany z firmą Librus ani przez nią wspierany; nazwa użyta wyłącznie
w celach identyfikacyjnych.

## 🤝 Wkład

Pull requesty są mile widziane — zgłoś je przez
[Issues](https://github.com/LukMaverick/LibrusSynergiaHA/issues) lub bezpośrednio
jako PR.

### 🙏 Podziękowania

Specjalne podziękowania dla **KB** za wsparcie i pomoc w rozwoju projektu.

## 👨‍💻 Autor

Stworzono na bazie biblioteki [librus-apix](https://github.com/poroknights/librus-apix)

---

**⭐ Jeśli podoba Ci się projekt, zostaw gwiazdkę na GitHub!**

## ☕ Wesprzyj projekt

Jeśli integracja jest dla Ciebie przydatna, możesz postawić kawę 😊

[![Buy Me A Coffee](https://img.shields.io/badge/Buy%20Me%20A%20Coffee-ffdd00?style=for-the-badge&logo=buy-me-a-coffee&logoColor=black)](https://buymeacoffee.com/LukMaverick)