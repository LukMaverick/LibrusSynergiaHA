"""Test the Librus APIX integration."""

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from unittest.mock import AsyncMock, patch, MagicMock

from custom_components.librus_apix.const import DOMAIN


@pytest.fixture
def mock_config_entry():
    """Return a mock config entry."""
    return ConfigEntry(
        version=1,
        domain=DOMAIN,
        title="Test Librus",
        data={"username": "test_user", "password": "test_password"},
        source="user",
        entry_id="test_entry_id"
    )


@pytest.fixture
def mock_librus_client():
    """Return a mock Librus client."""
    client = MagicMock()
    client.async_authenticate = AsyncMock(return_value=True)
    client.async_get_grades = AsyncMock(return_value=[
        {
            'subject': 'Mathematyka',
            'grade': '5',
            'date': '2025-01-01',
            'category': 'Test',
            'teacher': 'Jan Kowalski',
            'type': 'numeric'
        }
    ])
    client.async_get_messages = AsyncMock(return_value=[])
    return client


async def test_setup_entry(hass: HomeAssistant, mock_config_entry, mock_librus_client):
    """Test the setup entry."""
    with patch(
        "custom_components.librus_apix.LibrusApiClient",
        return_value=mock_librus_client
    ):
        result = await hass.config_entries.async_setup(mock_config_entry.entry_id)
        assert result is True


async def test_unload_entry(hass: HomeAssistant, mock_config_entry, mock_librus_client):
    """Test unloading an entry."""
    with patch(
        "custom_components.librus_apix.LibrusApiClient",
        return_value=mock_librus_client
    ):
        # Setup first
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        
        # Then unload
        result = await hass.config_entries.async_unload(mock_config_entry.entry_id)
        assert result is True