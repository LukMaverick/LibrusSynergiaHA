"""Constants for the Librus APIX integration."""

from datetime import timedelta

DOMAIN = "librus_apix"
DEFAULT_NAME = "Librus"

# Configuration keys
CONF_USERNAME = "username"
CONF_PASSWORD = "password"

# Update intervals
SCAN_INTERVAL = timedelta(hours=2)

# Default values
DEFAULT_MESSAGES_COUNT = 10

# Opcje (Options Flow)
CONF_FETCH_MESSAGE_CONTENT = "fetch_message_content"
DEFAULT_FETCH_MESSAGE_CONTENT = False

# Tresc wiadomosci: ile najnowszych wiadomosci i ile znakow tresci trzymac
# (atrybuty stanu HA maja limit 16 KB, wiec tresc jest przycinana).
MESSAGES_WITH_CONTENT = 5
MESSAGE_CONTENT_MAX_CHARS = 2000
