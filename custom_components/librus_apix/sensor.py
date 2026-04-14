"""Sensor platform for Librus APIX integration."""

import logging
from datetime import timedelta
from typing import Any, Dict, Optional

from homeassistant.components.sensor import SensorEntity, SensorDeviceClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import DOMAIN, SENSOR_TYPES, SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Librus APIX sensor platform."""
    client = hass.data[DOMAIN][config_entry.entry_id]
    
    coordinator = LibrusDataUpdateCoordinator(hass, client)
    await coordinator.async_config_entry_first_refresh()
    
    entities = []
    for sensor_type in SENSOR_TYPES:
        entities.append(LibrusApixSensor(coordinator, sensor_type, config_entry))
    
    async_add_entities(entities)


class LibrusDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching Librus data."""

    def __init__(self, hass: HomeAssistant, client):
        """Initialize."""
        self.client = client
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )

    async def _async_update_data(self):
        """Update data via library."""
        try:
            grades = await self.client.async_get_grades()
            messages = await self.client.async_get_messages(count=5)
            
            if grades is None or messages is None:
                raise UpdateFailed("Failed to update data")
            
            # Calculate statistics
            numeric_grades = [g for g in grades if g['grade'].replace('+', '').replace('-', '').isdigit()]
            
            # Calculate average (simplified - basic numeric conversion)
            grade_values = []
            for grade in numeric_grades:
                try:
                    base_grade = float(grade['grade'][0])
                    if '+' in grade['grade']:
                        base_grade += 0.5
                    elif '-' in grade['grade']:
                        base_grade -= 0.25
                    grade_values.append(base_grade)
                except:
                    pass
            
            average = sum(grade_values) / len(grade_values) if grade_values else 0
            
            # Get latest grade
            latest_grade = None
            if grades:
                sorted_grades = sorted(grades, key=lambda x: x['date'], reverse=True)
                latest_grade = sorted_grades[0]
            
            # Get latest message
            latest_message = messages[0] if messages else None
            
            return {
                'grades': grades,
                'grades_count': len(grades),
                'average_grade': round(average, 2),
                'latest_grade': latest_grade,
                'messages': messages,
                'messages_count': len(messages),
                'latest_message': latest_message,
            }
            
        except Exception as err:
            raise UpdateFailed(f"Error communicating with API: {err}")


class LibrusApixSensor(SensorEntity):
    """Implementation of a Librus APIX sensor."""

    def __init__(self, coordinator: LibrusDataUpdateCoordinator, sensor_type: str, config_entry: ConfigEntry):
        """Initialize the sensor."""
        self.coordinator = coordinator
        self.sensor_type = sensor_type
        self.config_entry = config_entry
        self._attr_name = f"Librus {SENSOR_TYPES[sensor_type]['name']}"
        self._attr_unique_id = f"{config_entry.entry_id}_{sensor_type}"
        self._attr_icon = SENSOR_TYPES[sensor_type]['icon']
        if SENSOR_TYPES[sensor_type]['unit']:
            self._attr_native_unit_of_measurement = SENSOR_TYPES[sensor_type]['unit']

    @property
    def device_info(self):
        """Return device information."""
        return {
            "identifiers": {(DOMAIN, self.config_entry.entry_id)},
            "name": "Librus APIX",
            "manufacturer": "Librus",
            "model": "APIX Integration",
        }

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.last_update_success

    @property
    def native_value(self):
        """Return the state of the sensor."""
        data = self.coordinator.data
        
        if self.sensor_type == "grades_count":
            return data.get('grades_count', 0)
        elif self.sensor_type == "average_grade":
            return data.get('average_grade', 0)
        elif self.sensor_type == "latest_grade":
            latest = data.get('latest_grade')
            if latest:
                return f"{latest['grade']} ({latest['subject']})"
            return "No grades"
        elif self.sensor_type == "messages":
            return data.get('messages_count', 0)
        elif self.sensor_type == "latest_message":
            latest = data.get('latest_message')
            if latest:
                return f"Od: {latest.author} - {latest.title}"
            return "No messages"
        elif self.sensor_type == "grades":
            return len(data.get('grades', []))
        
        return None

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        data = self.coordinator.data
        attributes = {}
        
        if self.sensor_type == "grades":
            grades = data.get('grades', [])
            # Group by subject
            by_subject = {}
            for grade in grades:
                subject = grade['subject']
                if subject not in by_subject:
                    by_subject[subject] = []
                by_subject[subject].append({
                    'grade': grade['grade'],
                    'date': grade['date'],
                    'category': grade['category'],
                    'teacher': grade['teacher']
                })
            attributes['grades_by_subject'] = by_subject
            attributes['total_grades'] = len(grades)
            
        elif self.sensor_type == "latest_grade":
            latest = data.get('latest_grade')
            if latest:
                attributes.update({
                    'subject': latest['subject'],
                    'grade': latest['grade'],
                    'date': latest['date'],
                    'category': latest['category'],
                    'teacher': latest['teacher']
                })
                
        elif self.sensor_type == "messages":
            messages = data.get('messages', [])
            attributes['messages'] = [
                {
                    'author': msg.author,
                    'title': msg.title,
                    'date': msg.date
                } for msg in messages
            ]
            
        elif self.sensor_type == "latest_message":
            latest = data.get('latest_message')
            if latest:
                attributes.update({
                    'author': latest.author,
                    'title': latest.title,
                    'date': latest.date
                })
        
        return attributes

    async def async_added_to_hass(self):
        """When entity is added to hass."""
        await self.coordinator.async_add_listener(self.async_write_ha_state)

    async def async_will_remove_from_hass(self):
        """When entity will be removed from hass."""
        await self.coordinator.async_remove_listener(self.async_write_ha_state)