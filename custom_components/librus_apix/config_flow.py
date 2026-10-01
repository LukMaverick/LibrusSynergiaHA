"""Config flow (logowanie) i options flow (bramka SMS, interwal) dla Librus APIX."""

import asyncio
import logging

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector

from librus_apix.client import new_client

from .const import (
    CONF_PUSH_NOTIFY,
    CONF_SCAN_INTERVAL,
    CONF_SCAN_INTERVAL_SZKOLA,
    CONF_SZKOLA_DNI_ROBOCZE,
    CONF_SZKOLA_DO,
    CONF_SZKOLA_OD,
    CONF_SMS_ENABLED,
    CONF_SMS_HEADERS,
    CONF_SMS_METHOD,
    CONF_SMS_TEKST_OCENY,
    CONF_SMS_TEKST_UWAGI,
    CONF_SMS_URL_OCENY,
    CONF_SMS_URL_UWAGI,
    CONF_SMS_VERIFY_SSL,
    CONF_WYSLIJ_TEST,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL_SZKOLA,
    DEFAULT_SZKOLA_DNI_ROBOCZE,
    DEFAULT_SZKOLA_DO,
    DEFAULT_SZKOLA_OD,
    DEFAULT_SMS_ENABLED,
    DEFAULT_SMS_METHOD,
    DEFAULT_SMS_TEKST_OCENY,
    DEFAULT_SMS_TEKST_UWAGI,
    DEFAULT_SMS_VERIFY_SSL,
    DOMAIN,
    MIN_SCAN_INTERVAL,
    SMS_METHODS,
    TYP_OCENA,
)
from .sms import (
    async_powiadom,
    dane_testowe,
    podziel_adresy,
    podziel_uslugi_notify,
    waliduj_adresy,
    waliduj_naglowki,
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
    def async_get_options_flow(config_entry: config_entries.ConfigEntry) -> "OptionsFlowHandler":
        """Zwroc handler opcji (przycisk 'Konfiguruj' przy integracji)."""
        return OptionsFlowHandler(config_entry)

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
    """Opcje integracji: bramka SMS (adresy, tresc, SSL) i interwal odswiezania.

    Zapisywane w entry.options (plik .storage/core.config_entries), wiec
    aktualizacja wtyczki (HACS) ich nie nadpisuje.
    """

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Inicjalizacja."""
        # Uwaga: nie nadpisujemy self.config_entry (w nowszych HA to wlasciwosc tylko do odczytu)
        self._entry = config_entry
        self._nowe_opcje: dict | None = None

    async def async_step_init(self, user_input: dict | None = None) -> FlowResult:
        """Jedyny krok formularza opcji."""
        errors: dict = {}
        opcje = dict(self._entry.options)

        if user_input is not None:
            # TextSelector moze nie przekazac pustego pola - uzupelnij pustymi wartosciami
            user_input.setdefault(CONF_SMS_URL_OCENY, "")
            user_input.setdefault(CONF_SMS_URL_UWAGI, "")
            user_input.setdefault(CONF_SMS_TEKST_OCENY, DEFAULT_SMS_TEKST_OCENY)
            user_input.setdefault(CONF_SMS_TEKST_UWAGI, DEFAULT_SMS_TEKST_UWAGI)
            user_input.setdefault(CONF_PUSH_NOTIFY, "")
            user_input.setdefault(CONF_SMS_HEADERS, "")

            bledne = waliduj_adresy(user_input[CONF_SMS_URL_OCENY]) + waliduj_adresy(
                user_input[CONF_SMS_URL_UWAGI]
            )
            if bledne:
                errors["base"] = "sms_url_invalid"
            elif waliduj_naglowki(user_input[CONF_SMS_HEADERS]):
                errors["base"] = "sms_headers_invalid"
            elif user_input.get(CONF_SMS_ENABLED) and not (
                podziel_adresy(user_input[CONF_SMS_URL_OCENY])
                or podziel_adresy(user_input[CONF_SMS_URL_UWAGI])
            ):
                errors["base"] = "sms_url_required"

            if not errors:
                wyslij_test = bool(user_input.pop(CONF_WYSLIJ_TEST, False))
                if wyslij_test:
                    return await self._async_test_i_pokaz_wynik(user_input)
                return self.async_create_entry(title="", data=user_input)
            opcje = user_input

        minuty = selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=MIN_SCAN_INTERVAL,
                max=1440,
                step=5,
                unit_of_measurement="min",
                mode=selector.NumberSelectorMode.BOX,
            )
        )
        schema = vol.Schema(
            {
                vol.Optional(
                    CONF_SZKOLA_OD, default=opcje.get(CONF_SZKOLA_OD, DEFAULT_SZKOLA_OD)
                ): selector.TimeSelector(),
                vol.Optional(
                    CONF_SZKOLA_DO, default=opcje.get(CONF_SZKOLA_DO, DEFAULT_SZKOLA_DO)
                ): selector.TimeSelector(),
                vol.Optional(
                    CONF_SZKOLA_DNI_ROBOCZE,
                    default=opcje.get(CONF_SZKOLA_DNI_ROBOCZE, DEFAULT_SZKOLA_DNI_ROBOCZE),
                ): selector.BooleanSelector(),
                vol.Optional(
                    CONF_SCAN_INTERVAL_SZKOLA,
                    default=opcje.get(CONF_SCAN_INTERVAL_SZKOLA, DEFAULT_SCAN_INTERVAL_SZKOLA),
                ): minuty,
                vol.Optional(
                    CONF_SCAN_INTERVAL,
                    default=opcje.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
                ): minuty,
                vol.Optional(
                    CONF_SMS_ENABLED,
                    default=opcje.get(CONF_SMS_ENABLED, DEFAULT_SMS_ENABLED),
                ): selector.BooleanSelector(),
                vol.Optional(
                    CONF_SMS_METHOD,
                    default=opcje.get(CONF_SMS_METHOD, DEFAULT_SMS_METHOD),
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=list(SMS_METHODS),
                        mode=selector.SelectSelectorMode.DROPDOWN,
                        translation_key=CONF_SMS_METHOD,
                    )
                ),
                vol.Optional(
                    CONF_SMS_HEADERS,
                    description={"suggested_value": opcje.get(CONF_SMS_HEADERS, "")},
                ): selector.TextSelector(selector.TextSelectorConfig(multiline=True)),
                vol.Optional(
                    CONF_SMS_VERIFY_SSL,
                    default=opcje.get(CONF_SMS_VERIFY_SSL, DEFAULT_SMS_VERIFY_SSL),
                ): selector.BooleanSelector(),
                vol.Optional(
                    CONF_SMS_URL_OCENY,
                    description={"suggested_value": opcje.get(CONF_SMS_URL_OCENY, "")},
                ): selector.TextSelector(selector.TextSelectorConfig(multiline=True)),
                vol.Optional(
                    CONF_SMS_TEKST_OCENY,
                    description={
                        "suggested_value": opcje.get(CONF_SMS_TEKST_OCENY, DEFAULT_SMS_TEKST_OCENY)
                    },
                ): selector.TextSelector(selector.TextSelectorConfig()),
                vol.Optional(
                    CONF_SMS_URL_UWAGI,
                    description={"suggested_value": opcje.get(CONF_SMS_URL_UWAGI, "")},
                ): selector.TextSelector(selector.TextSelectorConfig(multiline=True)),
                vol.Optional(
                    CONF_SMS_TEKST_UWAGI,
                    description={
                        "suggested_value": opcje.get(CONF_SMS_TEKST_UWAGI, DEFAULT_SMS_TEKST_UWAGI)
                    },
                ): selector.TextSelector(selector.TextSelectorConfig()),
                vol.Optional(
                    CONF_PUSH_NOTIFY,
                    description={"suggested_value": opcje.get(CONF_PUSH_NOTIFY, "")},
                ): selector.TextSelector(selector.TextSelectorConfig(multiline=True)),
                vol.Optional(CONF_WYSLIJ_TEST, default=False): selector.BooleanSelector(),
            }
        )

        return self.async_show_form(step_id="init", data_schema=schema, errors=errors)

    async def _async_test_i_pokaz_wynik(self, opcje: dict) -> FlowResult:
        """Wyslij testowy SMS/push wg wlasnie wpisanych opcji i pokaz wynik przed zapisaniem."""
        self._nowe_opcje = opcje
        dane_wpisu = (self.hass.data.get(DOMAIN) or {}).get(self._entry.entry_id) or {}
        coordinator = dane_wpisu.get("coordinator")
        info = (getattr(coordinator, "data", None) or {}).get("student_info")
        uczen = getattr(info, "name", "") or ""

        adresy = podziel_adresy(opcje.get(CONF_SMS_URL_OCENY, "")) if opcje.get(CONF_SMS_ENABLED) else []
        uslugi = podziel_uslugi_notify(opcje.get(CONF_PUSH_NOTIFY, ""))
        try:
            wynik = await async_powiadom(self.hass, opcje, TYP_OCENA, dane_testowe(TYP_OCENA, uczen))
        except Exception as ex:  # pylint: disable=broad-except
            _LOGGER.exception("Test powiadomien z opcji nie powiodl sie")
            wynik = {"sms": 0, "push": 0, "blad": str(ex)}

        return self.async_show_form(
            step_id="test",
            data_schema=vol.Schema({}),
            description_placeholders={
                "sms_ok": str(wynik.get("sms", 0)),
                "sms_all": str(len(adresy)),
                "push_ok": str(wynik.get("push", 0)),
                "push_all": str(len(uslugi)),
                "blad": wynik.get("blad", ""),
            },
        )

    async def async_step_test(self, user_input: dict | None = None) -> FlowResult:
        """Ekran z wynikiem testu - 'Przeslij' zapisuje opcje."""
        return self.async_create_entry(title="", data=self._nowe_opcje or {})
