"""Constants for the Librus APIX integration."""

from datetime import timedelta

DOMAIN = "librus_apix"
DEFAULT_NAME = "Librus"

# Configuration keys
CONF_USERNAME = "username"
CONF_PASSWORD = "password"

# Update intervals
SCAN_INTERVAL = timedelta(hours=2)
TIMETABLE_REFRESH = timedelta(hours=4)

# Default values
DEFAULT_MESSAGES_COUNT = 10

# Plan lekcji
DNI_TYGODNIA_PL = [
    "poniedziałek",
    "wtorek",
    "środa",
    "czwartek",
    "piątek",
    "sobota",
    "niedziela",
]
SKROTY_DNI_PL = ["Pn", "Wt", "Śr", "Cz", "Pt", "So", "Nd"]

# Okno tygodni dostepne przez usluge pobierz_tydzien (wzgledem biezacego tygodnia)
TYDZIEN_OKNO_WSTECZ = 2
TYDZIEN_OKNO_NAPRZOD = 4
TYDZIEN_CACHE_TTL = timedelta(hours=1)

# Godzina uznawana za koniec zajec, gdy brak lekcji w planie
KONIEC_ZAJEC_DOMYSLNIE = "15:00"

# Zadania domowe
ZADANIA_WSTECZ_DNI = 7
ZADANIA_NAPRZOD_DNI = 30
ZADANIA_TRESC_HORYZONT_DNI = 7
ZADANIA_TRESC_LIMIT_NA_CYKL = 5
ZADANIA_TRESC_MAX_ZNAKOW = 300

# Typy zdarzen terminarza. Kolejnosc ma znaczenie: pierwsza pasujaca regula wygrywa.
# Slowa kluczowe sa porownywane po normalizacji (male litery, bez polskich znakow).
REGULY_TYPOW = [
    ("odwolane", ["odwolan"]),
    ("dzien_wolny", ["dzien wolny", "dni wolne", "wolne od zajec", "ferie", "przerwa swiateczna", "dyrektorski", "dzien dyrektorski"]),
    ("kartkowka", ["kartkowk"]),
    ("sprawdzian", ["sprawdzian", "klasowk", "praca klasowa", "pisemn", "test"]),
    ("wycieczka", ["wycieczk", "wyjscie", "wyjazd"]),
    ("rada", ["rada pedagogiczna"]),
    ("zebranie", ["zebranie", "wywiadowk"]),
]
TYP_DOMYSLNY = "inne"

IKONY_TYPOW = {
    "sprawdzian": "📝",
    "kartkowka": "📝",
    "zadanie": "🏠",
    "odwolane": "❌",
    "dzien_wolny": "🎉",
    "wycieczka": "🚌",
    "rada": "👥",
    "zebranie": "👥",
    "inne": "📌",
}

# Typy zdarzen, ktore zawsze trafiaja na poziom dnia (nie do konkretnej lekcji)
TYPY_CALODNIOWE = {"dzien_wolny", "wycieczka", "rada", "zebranie"}
TYPY_SPRAWDZIAN = {"sprawdzian", "kartkowka"}

# Wersja integracji (zgodna z manifest.json); karta JS porownuje ja ze swoja
VERSION = "1.3.0"
