"""The Librus APIX integration."""

import asyncio
import logging
from typing import Dict, Any

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers import config_validation as cv

from librus_apix.client import Client, new_client

from .const import DOMAIN, SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["sensor"]

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_USERNAME): cv.string,
                vol.Required(CONF_PASSWORD): cv.string,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


class LibrusApiClient:
    """Class to interface with the Librus API."""

    def __init__(self, username: str, password: str):
        """Initialize the client."""
        self.username = username
        self.password = password
        self._client: Client = None
        self._token = None

    async def async_authenticate(self):
        """Authenticate with Librus API."""
        try:
            loop = asyncio.get_event_loop()
            self._client = await loop.run_in_executor(None, new_client)
            self._token = await loop.run_in_executor(
                None, self._client.get_token, self.username, self.password
            )
            return True
        except Exception as ex:
            _LOGGER.error("Authentication failed: %s", ex)
            return False

    async def async_get_grades(self):
        """Get grades from Librus."""
        try:
            if not self._client or not self._token:
                if not await self.async_authenticate():
                    return None

            from librus_apix.grades import get_grades
            
            loop = asyncio.get_event_loop()
            numeric_grades, average_grades, descriptive_grades = await loop.run_in_executor(
                None, get_grades, self._client, "all"
            )
            
            # Process all grades
            all_grades = []
            
            # Process numeric grades
            for subject_grades in numeric_grades:
                for subject, grades_list in subject_grades.items():
                    for grade in grades_list:
                        all_grades.append({
                            'subject': subject,
                            'grade': grade.grade,
                            'date': grade.date,
                            'category': grade.category,
                            'teacher': getattr(grade, 'teacher', ''),
                            'type': 'numeric'
                        })
            
            # Process descriptive grades (many are actually numeric)
            for subject_grades in descriptive_grades:
                for subject, grades_list in subject_grades.items():
                    for desc_grade in grades_list:
                        grade_val = desc_grade.grade.strip()
                        if grade_val and (grade_val.replace('+', '').replace('-', '').isdigit() or 
                                        grade_val in ['1', '2', '3', '4', '5', '6', '1+', '1-', '2+', '2-', 
                                                     '3+', '3-', '4+', '4-', '5+', '5-', '6+', '6-']):
                            all_grades.append({
                                'subject': subject,
                                'grade': desc_grade.grade,
                                'date': desc_grade.date,
                                'category': getattr(desc_grade, 'desc', '').split('\n')[0] if hasattr(desc_grade, 'desc') else '',
                                'teacher': getattr(desc_grade, 'teacher', ''),
                                'type': 'descriptive'
                            })
            
            return all_grades
            
        except Exception as ex:
            _LOGGER.error("Failed to get grades: %s", ex)
            return None

    async def async_get_messages(self, count: int = 5):
        """Get latest messages from Librus."""
        try:
            if not self._client or not self._token:
                if not await self.async_authenticate():
                    return None

            from librus_apix.messages import get_received
            
            loop = asyncio.get_event_loop()
            messages = await loop.run_in_executor(
                None, get_received, self._client, 1
            )
            
            # Return only the requested count
            return messages[:count] if messages else []
            
        except Exception as ex:
            _LOGGER.error("Failed to get messages: %s", ex)
            return None


async def async_setup(hass: HomeAssistant, config: Dict[str, Any]) -> bool:
    """Set up the Librus APIX component."""
    hass.data.setdefault(DOMAIN, {})
    
    if DOMAIN in config:
        username = config[DOMAIN][CONF_USERNAME]
        password = config[DOMAIN][CONF_PASSWORD]
        
        client = LibrusApiClient(username, password)
        hass.data[DOMAIN]["client"] = client
        
        # Test authentication
        if not await client.async_authenticate():
            _LOGGER.error("Failed to authenticate")
            return False

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Librus APIX from a config entry."""
    username = entry.data[CONF_USERNAME]
    password = entry.data[CONF_PASSWORD]
    
    client = LibrusApiClient(username, password)
    
    # Test authentication
    if not await client.async_authenticate():
        _LOGGER.error("Failed to authenticate")
        return False
    
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = client
    
    # Setup platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    
    return unload_ok