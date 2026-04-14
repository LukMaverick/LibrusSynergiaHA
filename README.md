# 🎓 Librus APIX Integration for Home Assistant

Integracja Home Assistant z systemem Librus Synergia, umożliwiająca monitorowanie ocen, wiadomości i innych danych szkolnych.

## ✨ Funkcje

- 📊 **Monitoring ocen** - wszystkie oceny ze wszystkich przedmiotów
- 📈 **Statystyki** - średnie ocen, liczba ocen, trend
- 📧 **Wiadomości** - najnowsze wiadomości z dziennika
- 🔔 **Powiadomienia** - automatyczne powiadomienia o nowych ocenach/wiadomościach
- 🏠 **Dashboard** - piękne karty w Home Assistant

## 🚀 Sensory

Integracja tworzy następujące sensory:

- `sensor.librus_grades` - Wszystkie oceny z atrybutami
- `sensor.librus_latest_grade` - Najnowsza ocena  
- `sensor.librus_total_grades` - Liczba wszystkich ocen
- `sensor.librus_average_grade` - Średnia wszystkich ocen
- `sensor.librus_unread_messages` - Liczba nieprzeczytanych wiadomości
- `sensor.librus_latest_message` - Najnowsza wiadomość

## 📦 Instalacja

### Opcja 1: HACS (Zalecana)

1. Otwórz HACS w Home Assistant
2. Idź do "Integrations"  
3. Kliknij "+" i wybierz "Custom repositories"
4. Dodaj: `https://github.com/LukMaverick/LibrusSynergiaHA`
5. Wybierz kategorię "Integration" 
6. Zainstaluj "Librus Synergia HA"
7. Restartuj Home Assistant

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

### Karta ocen
```yaml
type: entities
title: "📚 Oceny Librus"
entities:
  - entity: sensor.librus_latest_grade
    name: "Najnowsza ocena"
  - entity: sensor.librus_average_grade  
    name: "Średnia ocen"
  - entity: sensor.librus_total_grades
    name: "Liczba ocen"
```

### Karta wiadomości
```yaml
type: entities
title: "📧 Wiadomości Librus"
entities:
  - entity: sensor.librus_latest_message
    name: "Najnowsza wiadomość"
  - entity: sensor.librus_unread_messages
    name: "Nieprzeczytane"
```

### Karta trendu ocen
```yaml
type: gauge
entity: sensor.librus_average_grade
name: "Średnia ocen"
min: 1
max: 6
severity:
  green: 5
  yellow: 4
  red: 3
```

## 🔔 Przykładowe automatyzacje

### Powiadomienie o nowej ocenie
```yaml
automation:
  - alias: "Nowa ocena w Librus"
    trigger:
      platform: state
      entity_id: sensor.librus_latest_grade
    condition:
      - condition: template
        value_template: "{{ trigger.to_state.state != trigger.from_state.state }}"
    action:
      - service: notify.mobile_app_your_phone
        data:
          title: "🎓 Nowa ocena!"
          message: "{{ trigger.to_state.state }}"
```

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

## 👨‍💻 Autor

Stworzono na bazie biblioteki [librus-apix](https://github.com/RustySnek/librus-apix)

---

**⭐ Jeśli podoba Ci się projekt, zostaw gwiazdkę na GitHub!**