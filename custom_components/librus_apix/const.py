"""Constants for the Librus APIX integration."""

from datetime import timedelta

DOMAIN = "librus_apix"
DEFAULT_NAME = "Librus"

# Configuration keys
CONF_USERNAME = "username"
CONF_PASSWORD = "password"

# Opcje integracji (Ustawienia -> Integracje -> Librus -> Konfiguruj)
# Przechowywane w entry.options, wiec przetrwaja aktualizacje wtyczki.
CONF_SCAN_INTERVAL = "scan_interval"  # minuty - poza godzinami szkoly
CONF_SCAN_INTERVAL_SZKOLA = "scan_interval_szkola"  # minuty - w godzinach szkoly
CONF_SZKOLA_OD = "szkola_od"  # "HH:MM:SS" poczatek okna szkolnego
CONF_SZKOLA_DO = "szkola_do"  # "HH:MM:SS" koniec okna szkolnego
CONF_SZKOLA_DNI_ROBOCZE = "szkola_dni_robocze"  # okno szkolne tylko pon-pt
CONF_SMS_ENABLED = "sms_enabled"
CONF_SMS_VERIFY_SSL = "sms_verify_ssl"
CONF_SMS_URL_OCENY = "sms_url_oceny"
CONF_SMS_URL_UWAGI = "sms_url_uwagi"
CONF_SMS_TEKST_OCENY = "sms_tekst_oceny"
CONF_SMS_TEKST_UWAGI = "sms_tekst_uwagi"
CONF_SMS_METHOD = "sms_method"
CONF_SMS_HEADERS = "sms_headers"  # naglowki HTTP "Nazwa: wartosc" (jeden na linie)
CONF_PUSH_NOTIFY = "push_notify"  # uslugi notify.* (jedna na linie)
CONF_WYSLIJ_TEST = "wyslij_test"  # tylko w formularzu opcji: po zapisaniu wyslij testowy SMS/push (nie jest zapisywane)

# Metody HTTP bramki
METHOD_GET = "get"            # parametry w adresie (query string)
METHOD_POST = "post"          # parametry z adresu wysylane w body (application/x-www-form-urlencoded)
METHOD_POST_JSON = "post_json"  # parametry z adresu wysylane w body jako JSON
SMS_METHODS = (METHOD_GET, METHOD_POST, METHOD_POST_JSON)

DEFAULT_SCAN_INTERVAL = 120  # minuty (poza szkola)
DEFAULT_SCAN_INTERVAL_SZKOLA = 55  # minuty (w szkole: lekcja 45 min + przerwa)
DEFAULT_SZKOLA_OD = "07:00:00"
DEFAULT_SZKOLA_DO = "15:00:00"
DEFAULT_SZKOLA_DNI_ROBOCZE = True
MIN_SCAN_INTERVAL = 15
DEFAULT_SMS_ENABLED = False
DEFAULT_SMS_VERIFY_SSL = True
DEFAULT_SMS_METHOD = METHOD_GET
DEFAULT_PUSH_TYTUL_OCENY = "🎓 Librus: nowa ocena %ocena%"
DEFAULT_PUSH_TYTUL_UWAGI = "⚠️ Librus: nowa uwaga"
DEFAULT_SMS_TEKST_OCENY = "Librus %uczen%: nowa ocena %ocena% z %przedmiot% (%kategoria%, waga %waga%), srednia %srednia% %komentarz%"
DEFAULT_SMS_TEKST_UWAGI = "Librus %uczen%: nowa uwaga (%rodzaj%, %kategoria%) od %nauczyciel%: %tresc%"

# Placeholdery dostepne w adresach bramki SMS (zamieniane na wartosc zakodowana URL)
SMS_PLACEHOLDERS = (
    "tekst",       # gotowa tresc SMS zbudowana z szablonu tresci (tylko w adresie URL)
    "typ",         # "ocena" lub "uwaga"
    "uczen",       # imie i nazwisko ucznia
    "przedmiot",   # oceny
    "ocena",       # oceny
    "kategoria",   # oceny i uwagi
    "nauczyciel",  # oceny i uwagi
    "data",        # oceny i uwagi
    "waga",        # oceny
    "komentarz",   # oceny (jesli nauczyciel dodal)
    "srednia",     # oceny - wyliczona srednia wazona z przedmiotu po tej ocenie
    "tresc",       # uwagi
    "rodzaj",      # uwagi (np. uwaga / pochwala)
)
SMS_TIMEOUT = 15  # sekundy

# Akcja (serwis) HA
SERVICE_WYSLIJ_SMS = "wyslij_sms"
ATTR_TYP = "typ"
ATTR_URL = "url"
ATTR_PUSH = "push"
TYP_OCENA = "ocena"
TYP_UWAGA = "uwaga"

# Update intervals (domyslny; realny interwal z opcji CONF_SCAN_INTERVAL)
SCAN_INTERVAL = timedelta(minutes=DEFAULT_SCAN_INTERVAL)

# Magazyn HA (.storage) z lista juz widzianych ocen/uwag/wiadomosci
STORAGE_VERSION = 1
STORAGE_KEY = f"{DOMAIN}.seen"

# Default values
DEFAULT_MESSAGES_COUNT = 10
