# 🚀 Quick Start Guide

## Uruchomienie środowiska testowego

### Windows (PowerShell)
```powershell
.\start.ps1
```

### Linux/macOS (Bash)
```bash
chmod +x start.sh
./start.sh
```

### Manual Start
```bash
# Uruchom kontenery
docker-compose up -d

# Sprawdź status
docker ps

# Wyświetl logi
docker-compose logs -f homeassistant
```

## Dostęp do aplikacji

- **Home Assistant**: http://localhost:8123
- **Code Server**: http://localhost:8443 (hasło: homeassistant)

## Pierwsze uruchomienie

1. Otwórz http://localhost:8123
2. Przejdź przez kreator konfiguracji HA
3. Idź do `Configuration` > `Integrations`
4. Kliknij `+ ADD INTEGRATION`
5. Wyszukaj `Librus APIX`
6. Podaj swoje dane logowania do Librus
7. Ciesz się nowymi sensorami! 🎉

## Karta terminarza

Karta `custom:librus-terminarz-card` rejestruje się automatycznie przy starcie. Po aktualizacji odśwież stronę
(Ctrl+Shift+R). W trybie YAML dodaj zasób `/librus_apix_static/librus-terminarz-card.js` (`type: module`).
Podgląd bez HA: `python3 -m http.server`, potem `custom_components/librus_apix/frontend/demo-terminarz.html`.

## Zatrzymanie

```bash
docker-compose down
```

## Troubleshooting

### Jeśli Home Assistant nie startuje
```bash
# Sprawdź logi
docker-compose logs homeassistant

# Restart
docker-compose restart homeassistant
```

### Jeśli integracja nie działa
```bash
# Sprawdź logi z debug
docker-compose logs homeassistant | grep librus
```

### Reset konfiguracji
```bash
# Usuń konfigurację i uruchom ponownie
rm -rf config/.storage
docker-compose restart homeassistant
```