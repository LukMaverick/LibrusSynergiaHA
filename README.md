# 🎓 Librus APIX Integration for Home Assistant

[![Buy Me A Coffee](https://img.shields.io/badge/Buy%20Me%20A%20Coffee-ffdd00?style=for-the-badge&logo=buy-me-a-coffee&logoColor=black)](https://buymeacoffee.com/LukMaverick)

Integracja Home Assistant z systemem Librus Synergia, umożliwiająca monitorowanie ocen, wiadomości i innych danych szkolnych.

## ✨ Funkcje

- 📊 **Monitoring ocen** - wszystkie oceny ze wszystkich przedmiotów
- 📈 **Statystyki** - średnie ocen, liczba ocen, trend
- 📧 **Wiadomości** - najnowsze wiadomości z dziennika (temat, nadawca)
- ⚠️ **Uwagi** - uwagi i pochwały ucznia
- 🔔 **Zdarzenia HA** - `librus_apix_nowa_ocena`, `librus_apix_nowa_uwaga`, `librus_apix_nowa_wiadomosc`, … do własnych automatyzacji
- 📲 **SMS przez własną bramkę** - nowa ocena / uwaga wysyłana HTTP (GET / POST / POST JSON) na Twój serwer SMS (wiele hostów, opcja bez weryfikacji SSL) — [konfiguracja](#-bramka-sms-własny-serwer)
- 📱 **Push na telefon** - przez usługi `notify.mobile_app_*` HA, bez pisania automatyzacji
- 🧪 **Przyciski testowe** - „Test powiadomień – ocena / uwaga” na urządzeniu Librus: klik i wychodzi testowy SMS/push
- 💾 **Pamięć w HA** - lista już widzianych ocen/uwag jest zapisywana w `.storage`, więc po restarcie HA nie ma duplikatów, a oceny wystawione w czasie przestoju też dojdą
- 🏠 **Dashboard** - piękne karty w Home Assistant

## 🚀 Sensory

Integracja tworzy następujące sensory:

| Sensor | Opis | Wartość |
|--------|------|---------|
| `sensor.librus_uczen` | Informacje o uczniu (klasa, wychowawca, szkoła) | imię i nazwisko |
| `sensor.librus_szczesliwy_numerek` | Szczęśliwy numerek dnia | numer |
| `sensor.librus_oceny` | Wszystkie oceny bieżącego semestru | liczba ocen |
| `sensor.librus_ostatnia_nowa_ocena` | **Ostatnia nowa ocena** (wykryta przy odświeżaniu); atrybuty: `przedmiot`, `data`, `kategoria`, `nauczyciel`, `waga`, `komentarz`, `srednia` | ocena, np. `4+` |
| `sensor.librus_srednia_ocen` | **Globalna średnia** ze wszystkich przedmiotów | float (wykres 📈) |
| `sensor.librus_wiadomosci` | Ostatnie 5 wiadomości (temat i nadawca — treść celowo nie jest pobierana, żeby nie oznaczać wiadomości jako przeczytanych) | liczba nieprzeczytanych |
| `sensor.librus_ostatnia_nowa_wiadomosc` | **Ostatnia nowa wiadomość**; atrybuty: `nadawca`, `data`, `nieprzeczytana`, `ma_zalacznik` | temat |
| `sensor.librus_uwagi` | Uwagi i pochwały ucznia (lista w atrybucie `uwagi`) | liczba uwag |
| `sensor.librus_ostatnia_nowa_uwaga` | **Ostatnia nowa uwaga**; atrybuty: `rodzaj`, `kategoria`, `nauczyciel`, `data` | treść uwagi |
| `sensor.librus_zadania` | Nadchodzące zadania domowe (30 dni) | liczba zadań |
| `sensor.librus_terminarz` | Nadchodzące zdarzenia z terminarza | liczba zdarzeń |
| `button.librus_test_powiadomien_ocena` | Wysyła **testowy** SMS/push „nowa ocena” skonfigurowanymi kanałami | przycisk |
| `button.librus_test_powiadomien_uwaga` | Wysyła **testowy** SMS/push „nowa uwaga” | przycisk |
| `sensor.librus_<przedmiot>` | Oceny z danego przedmiotu (np. `sensor.librus_matematyka`) | lista ocen: "4, 3+, 5" |
| `sensor.librus_srednia_<przedmiot>` | **Średnia** z danego przedmiotu (np. `sensor.librus_srednia_matematyka`) | float (wykres 📈) |

Sensory średnich mają `state_class: measurement` — HA automatycznie rysuje dla nich wykres historyczny po kliknięciu w encję.
Średnie są **ważone** (waga oceny, oceny „nie liczy do średniej” pomijane — tak jak liczy Librus); oficjalna średnia z Librusa jest dostępna w atrybucie `srednia_librus`. Każda ocena w atrybucie `oceny` ma pola `waga`, `liczy_do_sredniej`, `komentarz`.

> Rzeczywiste nazwy encji zależą od imienia ucznia (np. `sensor.librus_jan_kowalski_ostatnia_nowa_ocena`). Sprawdź je w **Narzędzia deweloperskie → Stany**.

Sensory „Ostatnia nowa …” pokazują ostatni element, który integracja wykryła jako **nowy** (i o którym wysłała zdarzenie/SMS). Zanim wykryje pierwszą nowość — pokazują najnowszy element wg daty.

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

### Opcje (przycisk „Konfiguruj”)

Po dodaniu integracji: **Ustawienia → Urządzenia i usługi → Librus Synergia HA → Konfiguruj**. Tam ustawisz:

- **Dwie pory sprawdzania**: w godzinach szkoły (domyślnie 07:00–15:00, pon–pt) co **55 min** (lekcja + przerwa), poza szkołą co **120 min** (minimum 15 min). Pierwsze poranne sprawdzenie jest dociągane do początku lekcji. Aktualny tryb i interwał widać w atrybutach `tryb_sprawdzania` / `interwal_minuty` sensora „Informacje o uczniu”.
- **bramkę SMS** — patrz sekcja [📲 Bramka SMS](#-bramka-sms-własny-serwer).

Opcje są zapisywane w bazie Home Assistant (`.storage/core.config_entries`), a nie w plikach wtyczki — **aktualizacja integracji przez HACS ich nie nadpisuje**.

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

## 📲 Bramka SMS (własny serwer)

Integracja może sama wysłać SMS o **nowej ocenie** i **nowej uwadze** przez Twój serwer/bramkę SMS —
wystarczy, że bramka przyjmuje zwykłe żądanie **HTTP GET** z parametrami w adresie.
Nie trzeba pisać automatyzacji: wszystko ustawia się w opcjach integracji.

### Jak to skonfigurować w Home Assistant

1. **Ustawienia → Urządzenia i usługi → Librus Synergia HA → Konfiguruj**.
2. Włącz **„Wysyłaj SMS przez własną bramkę”**.
3. W polu **„Adresy bramki – nowa ocena”** wpisz adres swojej bramki. Każda linia to osobny host / numer telefonu — SMS pójdzie na **wszystkie**:
   ```
   https://sms.example.pl/smsgateway/48600000000?text=%tekst%
   https://sms.example.pl/smsgateway/48600111222?text=%tekst%
   ```
   Bramka z osobnymi parametrami? Użyj placeholderów bezpośrednio:
   ```
   https://sms.example.pl/send?code=TAJNYKOD&przedmiot=%przedmiot%&ocena=%ocena%&konto=Max
   ```
4. W polu **„Treść SMS – nowa ocena”** ustaw treść (podstawiana pod `%tekst%`), np.
   `Librus %uczen%: nowa ocena %ocena% z %przedmiot% (%kategoria%)`.
5. To samo dla uwag: **„Adresy bramki – nowa uwaga”** i **„Treść SMS – nowa uwaga”**, np.
   `Librus %uczen%: uwaga od %nauczyciel%: %tresc%`. Puste pole adresów = SMS o uwagach nie są wysyłane.
6. **Metoda HTTP bramki**: domyślnie **GET** (parametry w adresie). Jeśli bramka wymaga **POST**, wybierz `POST` — parametry z części `?a=b&c=d` adresu zostaną wysłane w body jako formularz (`application/x-www-form-urlencoded`), a `POST JSON` wyśle je jako JSON `{"a": "b", "c": "d"}`. Adres wpisujesz zawsze tak samo.
7. **Nagłówki HTTP** (opcjonalnie): jeśli API wymaga tokenu w nagłówku, wpisz po jednym na linię, np. `Authorization: Bearer TWÓJ_TOKEN` lub `X-Api-Key: abc123`. HTTP Basic Auth możesz podać w adresie: `https://UŻYTKOWNIK:HASŁO@host/...`.
   Przykład **Twilio** (metoda `POST`, Basic auth w adresie):
   ```
   https://ACxxxxxxxx:TOKEN@api.twilio.com/2010-04-01/Accounts/ACxxxxxxxx/Messages.json?To=%2B48600000000&From=%2B1234567890&Body=%tekst%
   ```
   Jeśli bramka ma certyfikat self‑signed, wyłącz **„Sprawdzaj certyfikat SSL bramki”**.
8. (Opcjonalnie) **Push na telefon**: wpisz nazwę usługi powiadomień aplikacji HA, np. `mobile_app_iphone_marcina` (jedna na linię = kilka telefonów). Nazwę znajdziesz w **Narzędzia deweloperskie → Akcje** (wpisz `notify.mobile`). Push działa niezależnie od włącznika SMS.
9. **Prześlij** — integracja przeładuje się z nowymi ustawieniami.
10. **Przetestuj**: najprościej zaznacz na dole formularza **„Wyślij testowy SMS/push po kliknięciu Prześlij”** — po kliknięciu **Prześlij** integracja od razu wyśle testową ocenę i pokaże ekran z wynikiem (ile SMS/push wyszło); kolejne **Prześlij** zapisuje ustawienia. Alternatywnie na urządzeniu Librus (Ustawienia → Urządzenia → Librus – Imię) kliknij **„Test powiadomień – ocena”** lub **„– uwaga”**. Wyjdzie testowy SMS (i push) z przykładowymi danymi (ocena 5 z „Test (przedmiot)”). Jeśli nic nie jest skonfigurowane lub bramka odpowie błędem, HA pokaże komunikat, a szczegóły znajdziesz w logach.

**Co oznacza „Wysyłaj SMS przez własną bramkę”?** To główny włącznik SMS‑ów. Gdy jest wyłączony, integracja nie wywołuje adresów bramki (adresy zostają zapisane), ale nadal wysyła zdarzenia HA (`librus_apix_nowa_ocena`, `librus_apix_nowa_uwaga`) i push — automatyzacje działają normalnie.

Ustawienia trzymane są w Home Assistant, więc **aktualizacja wtyczki ich nie kasuje**.

### Placeholdery

| Placeholder | Znaczenie | Ocena | Uwaga |
|-------------|-----------|:-----:|:-----:|
| `%tekst%` | gotowa treść SMS z pola „Treść SMS” (tylko w adresie) | ✅ | ✅ |
| `%uczen%` | imię i nazwisko ucznia | ✅ | ✅ |
| `%typ%` | `ocena` lub `uwaga` | ✅ | ✅ |
| `%przedmiot%` | przedmiot | ✅ | — |
| `%ocena%` | ocena, np. `4+` | ✅ | — |
| `%kategoria%` | kategoria (np. Sprawdzian) | ✅ | ✅ |
| `%nauczyciel%` | nauczyciel | ✅ | ✅ |
| `%data%` | data | ✅ | ✅ |
| `%waga%` | waga oceny | ✅ | — |
| `%komentarz%` | komentarz nauczyciela do oceny (pusty, gdy brak) | ✅ | — |
| `%srednia%` | **średnia ważona** z przedmiotu po tej ocenie (wyliczona jak w Librusie) | ✅ | — |
| `%tresc%` | treść uwagi | — | ✅ |
| `%rodzaj%` | rodzaj uwagi (uwaga / pochwała) | — | ✅ |

Wartości wstawiane do adresu są automatycznie kodowane do URL (np. `4+` → `4%2B`, spacje → `%20`).

### Test bez czekania na nową ocenę

**Narzędzia deweloperskie → Akcje**, wybierz `Librus Synergia HA: Wyślij SMS przez bramkę` (`librus_apix.wyslij_sms`):

```yaml
action: librus_apix.wyslij_sms
data:
  typ: ocena
  ocena: "5"
  przedmiot: Matematyka
  kategoria: Sprawdzian
```

Akcja użyje adresów i treści z opcji integracji. Można też podać własny adres w polu `url` (jeden lub kilka — po jednym na linię), gotową treść w `tekst` oraz `push: true`, żeby wysłać też push. Najprościej jednak kliknąć przycisk **„Test powiadomień – ocena”** na urządzeniu Librus.

W logach (`Ustawienia → System → Logi`) zobaczysz `SMS wyslany przez sms.example.pl (HTTP 200)` albo błąd z odpowiedzią bramki. Włączenie logów `debug` (sekcja [Logi](#-logi)) pokaże pełny wywołany adres.

### Użycie akcji we własnej automatyzacji

```yaml
automation:
  - alias: "Librus - SMS o nowej ocenie ponizej 3"
    trigger:
      - platform: event
        event_type: librus_apix_nowa_ocena
    condition:
      - condition: template
        value_template: "{{ trigger.event.data.ocena[0] | int(6) < 3 }}"
    action:
      - action: librus_apix.wyslij_sms
        data:
          typ: ocena
          ocena: "{{ trigger.event.data.ocena }}"
          przedmiot: "{{ trigger.event.data.przedmiot }}"
          kategoria: "{{ trigger.event.data.kategoria }}"
          tekst: "UWAGA! {{ trigger.event.data.uczen }} dostal {{ trigger.event.data.ocena }} z {{ trigger.event.data.przedmiot }}"
```

> Jeśli używasz akcji w automatyzacji, wyłącz automatyczną wysyłkę w opcjach (albo zostaw puste pole adresów dla danego typu), żeby nie dostać dwóch SMS-ów.

## 🔔 Automatyzacje powiadomień na telefon

Integracja wysyła zdarzenia Home Assistant gdy pojawi się nowa wiadomość, ocena lub uwaga.
Zdarzenia są wykrywane przy każdym odświeżeniu (domyślnie co 55 min w godzinach szkoły i co 2 h poza nimi — ustawisz to w opcjach integracji).
Lista już widzianych elementów jest zapisywana w `.storage` Home Assistanta — pierwsze uruchomienie tylko zapamiętuje stan,
a po restarcie HA **nie ma duplikatów**; oceny wystawione w czasie, gdy HA nie działał, zostaną wykryte przy pierwszym odświeżeniu po starcie.

> **Test bez czekania:** Idź do **Developer Tools → Events**, Event type: `librus_apix_nowa_wiadomosc`, Event data jak poniżej i kliknij **Fire Event**.

### 📬 Powiadomienie o nowej wiadomości

Zdarzenie: `librus_apix_nowa_wiadomosc`  
Dostępne dane: `nadawca`, `temat`, `data`, `nieprzeczytana`, `ma_zalacznik`, `uczen`

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
Dostępne dane: `przedmiot`, `ocena`, `data`, `kategoria`, `nauczyciel`, `waga`, `liczy_do_sredniej`, `komentarz`, `srednia` (ważona, wyliczona), `srednia_librus` (oficjalna z Librusa, jeśli dostępna), `uczen`

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

### ⚠️ Powiadomienie o nowej uwadze

Zdarzenie: `librus_apix_nowa_uwaga`  
Dostępne dane: `tresc`, `rodzaj`, `kategoria`, `nauczyciel`, `data`, `uczen`

```yaml
automation:
  - alias: "Librus - nowa uwaga"
    trigger:
      platform: event
      event_type: librus_apix_nowa_uwaga
    action:
      - service: notify.mobile_app_NAZWA_TWOJEGO_TELEFONU
        data:
          title: "⚠️ Librus: nowa uwaga ({{ trigger.event.data.rodzaj }})"
          message: >-
            {{ trigger.event.data.nauczyciel }}: {{ trigger.event.data.tresc }}
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

## 👨‍💻 Autorzy

- Oryginalna integracja: [LukMaverick](https://github.com/LukMaverick/LibrusSynergiaHA)
- Fork i rozwój (bramka SMS, push, uwagi, średnie ważone, przyciski testowe): **Marcin Chuć** ([mchuc](https://github.com/mchuc)) — [![ORCID](https://img.shields.io/badge/ORCID-0000--0002--8430--9763-A6CE39?logo=orcid&logoColor=white)](https://orcid.org/0000-0002-8430-9763) <https://orcid.org/0000-0002-8430-9763>

Stworzono na bazie biblioteki [librus-apix](https://github.com/RustySnek/librus-apix)

---

**⭐ Jeśli podoba Ci się projekt, zostaw gwiazdkę na GitHub!**

## ☕ Wesprzyj projekt

Jeśli integracja jest dla Ciebie przydatna, możesz postawić kawę 😊

[![Buy Me A Coffee](https://img.shields.io/badge/Buy%20Me%20A%20Coffee-ffdd00?style=for-the-badge&logo=buy-me-a-coffee&logoColor=black)](https://buymeacoffee.com/LukMaverick)