"""Constants for the Librus APIX integration."""

from datetime import timedelta

DOMAIN = "librus_apix"
DEFAULT_NAME = "Librus"

# Configuration keys
CONF_USERNAME = "username"
CONF_PASSWORD = "password"

# Update intervals
SCAN_INTERVAL = timedelta(hours=2)

# Interwal odpytywania Librusa, konfigurowalny w opcjach integracji.
# Jeden cykl to 8 zapytan HTTP (oceny, wiadomosci, zadania, uczen,
# 2x terminarz, 2x plan lekcji), wiec nie schodzimy ponizej 15 minut.
CONF_SCAN_INTERVAL_MINUTES = "scan_interval_minutes"
DEFAULT_SCAN_INTERVAL_MINUTES = 120
MIN_SCAN_INTERVAL_MINUTES = 15
MAX_SCAN_INTERVAL_MINUTES = 1440

# Default values
DEFAULT_MESSAGES_COUNT = 10

# Ile dni lekcyjnych pokazuje czujnik planu
DEFAULT_PLAN_DAYS = 5
