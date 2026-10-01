"""Test the Librus APIX integration."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.librus_apix.const import DOMAIN


@pytest.fixture
def mock_config_entry(hass: HomeAssistant):
    """Return a mock config entry added to hass."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Test Librus",
        data={"username": "test_user", "password": "test_password"},
        entry_id="test_entry_id",
    )
    entry.add_to_hass(hass)
    return entry


@pytest.fixture
def mock_librus_client():
    """Return a mock Librus client."""
    client = MagicMock()
    client.async_authenticate = AsyncMock(return_value=True)
    client.async_get_grades = AsyncMock(return_value=[
        {
            'subject': 'Matematyka',
            'grade': '5',
            'date': '2025-01-01',
            'category': 'Test',
            'teacher': 'Jan Kowalski',
            'type': 'numeric'
        }
    ])
    client.async_get_messages = AsyncMock(return_value=[])
    client.async_get_homework = AsyncMock(return_value=[])
    client.async_get_schedule = AsyncMock(return_value=[])
    client.async_get_uwagi = AsyncMock(return_value=[])
    client.averages = {}
    client.async_get_student_information = AsyncMock(
        return_value=SimpleNamespace(name="Jan Testowy", class_name="5a", number=1, tutor="", school="", lucky_number=None)
    )
    return client


async def test_setup_entry(hass: HomeAssistant, mock_config_entry, mock_librus_client):
    """Test the setup entry."""
    with patch(
        "custom_components.librus_apix.LibrusApiClient",
        return_value=mock_librus_client
    ):
        result = await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
        assert result is True
        assert hass.states.get("sensor.oceny").state == "1"
        assert hass.services.has_service(DOMAIN, "wyslij_sms")


async def test_unload_entry(hass: HomeAssistant, mock_config_entry, mock_librus_client):
    """Test unloading an entry."""
    with patch(
        "custom_components.librus_apix.LibrusApiClient",
        return_value=mock_librus_client
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        result = await hass.config_entries.async_unload(mock_config_entry.entry_id)
        await hass.async_block_till_done()
        assert result is True
        assert mock_config_entry.entry_id not in hass.data[DOMAIN]
        assert not hass.services.has_service(DOMAIN, "wyslij_sms")
