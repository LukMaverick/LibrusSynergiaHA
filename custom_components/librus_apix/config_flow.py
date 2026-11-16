"""Config flow for Librus APIX integration."""

import logging
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult

from librus_apix.client import new_client

from .const import (
    CONF_FETCH_MESSAGE_CONTENT,
    DEFAULT_FETCH_MESSAGE_CONTENT,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


async def validate_input(hass: HomeAssistant, data: dict):
    """Validate the user input allows us to connect."""
    username = data[CONF_USERNAME]
    password = data[CONF_PASSWORD]
    
    # Test authentication
    try:
        import asyncio
        loop = asyncio.get_running_loop()
        client = await loop.run_in_executor(None, new_client)
        token = await loop.run_in_executor(None, client.get_token, username, password)
        
        if not token:
            raise ValueError("Authentication failed")
            
        return {"title": f"Librus APIX ({username})"}
    
    except Exception as ex:
        _LOGGER.error("Authentication error: %s", ex)
        raise ValueError("Cannot connect") from ex


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Librus APIX."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> "OptionsFlowHandler":
        """Return the options flow."""
        return OptionsFlowHandler()

    async def async_step_user(
        self, user_input: dict | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors = {}
        
        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)
            except ValueError:
                errors["base"] = "cannot_connect"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="user", 
            data_schema=STEP_USER_DATA_SCHEMA, 
            errors=errors
        )


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Opcje integracji Librus APIX."""

    async def async_step_init(self, user_input: dict | None = None) -> FlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current = self.config_entry.options.get(
            CONF_FETCH_MESSAGE_CONTENT, DEFAULT_FETCH_MESSAGE_CONTENT
        )
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_FETCH_MESSAGE_CONTENT, default=current): bool,
                }
            ),
        )
