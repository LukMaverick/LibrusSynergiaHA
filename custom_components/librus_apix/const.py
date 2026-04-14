"""Constants for the Librus APIX integration."""

from datetime import timedelta

DOMAIN = "librus_apix"
DEFAULT_NAME = "Librus APIX"

# Configuration keys
CONF_USERNAME = "username"
CONF_PASSWORD = "password"

# Update intervals
SCAN_INTERVAL = timedelta(hours=2)
MESSAGE_SCAN_INTERVAL = timedelta(minutes=30)

# Sensor types
SENSOR_TYPES = {
    "grades": {
        "name": "Grades",
        "icon": "mdi:school",
        "unit": None,
    },
    "latest_grade": {
        "name": "Latest Grade",
        "icon": "mdi:trophy",
        "unit": None,
    },
    "grades_count": {
        "name": "Total Grades",
        "icon": "mdi:counter",
        "unit": "grades",
    },
    "average_grade": {
        "name": "Average Grade",
        "icon": "mdi:calculator",
        "unit": None,
    },
    "messages": {
        "name": "Unread Messages",
        "icon": "mdi:message-text",
        "unit": "messages",
    },
    "latest_message": {
        "name": "Latest Message",
        "icon": "mdi:message-outline",
        "unit": None,
    },
}

# Default values
DEFAULT_MESSAGES_COUNT = 5