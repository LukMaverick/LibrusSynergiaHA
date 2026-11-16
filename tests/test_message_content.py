"""Testy opcjonalnego pobierania tresci wiadomosci."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.librus_apix.const import (
    CONF_FETCH_MESSAGE_CONTENT,
    MESSAGE_CONTENT_MAX_CHARS,
    MESSAGES_WITH_CONTENT,
)
from custom_components.librus_apix.sensor import (
    LibrusDataUpdateCoordinator,
    _przytnij_tresc,
)


def _msg(n: int) -> dict:
    return {
        "author": f"Nauczyciel {n}",
        "title": f"Temat {n}",
        "date": "2026-11-13 12:00:59",
        "href": f"href-{n}",
        "unread": True,
        "has_attachment": False,
    }


def _coordinator(hass, enabled: bool, content="Przynieść:\r\n\r\n\r\n- blok A3\r\n- klej"):
    client = MagicMock()
    client.async_get_message_content = AsyncMock(return_value=content)
    entry = MagicMock()
    entry.options = {CONF_FETCH_MESSAGE_CONTENT: enabled}
    return LibrusDataUpdateCoordinator(hass, client, entry), client


def test_przytnij_tresc_porzadkuje_i_przycina():
    assert _przytnij_tresc(None) == ""
    assert _przytnij_tresc("a\r\n\r\n\r\nb  \n") == "a\n\nb"
    dlugi = _przytnij_tresc("x" * (MESSAGE_CONTENT_MAX_CHARS + 50))
    assert len(dlugi) == MESSAGE_CONTENT_MAX_CHARS
    assert dlugi.endswith("…")


async def test_opcja_wylaczona_nie_pobiera(hass):
    coordinator, client = _coordinator(hass, enabled=False)
    assert coordinator._fetch_message_content is False


async def test_bez_config_entry_opcja_wylaczona(hass):
    coordinator = LibrusDataUpdateCoordinator(hass, MagicMock())
    assert coordinator._fetch_message_content is False


async def test_pobiera_tylko_najnowsze_i_tylko_raz(hass):
    coordinator, client = _coordinator(hass, enabled=True)
    messages = [_msg(n) for n in range(10)]

    await coordinator._attach_message_content(messages)

    assert client.async_get_message_content.await_count == MESSAGES_WITH_CONTENT
    assert messages[0]["content"] == "Przynieść:\n\n- blok A3\n- klej"
    assert "content" not in messages[MESSAGES_WITH_CONTENT]

    # Drugie odswiezenie: te same wiadomosci nie sa otwierane ponownie
    messages2 = [_msg(n) for n in range(10)]
    await coordinator._attach_message_content(messages2)
    assert client.async_get_message_content.await_count == MESSAGES_WITH_CONTENT
    assert messages2[0]["content"] == messages[0]["content"]


async def test_nowa_wiadomosc_pobierana_a_stare_usuwane_z_pamieci(hass):
    coordinator, client = _coordinator(hass, enabled=True)
    await coordinator._attach_message_content([_msg(n) for n in range(5)])
    client.async_get_message_content.reset_mock()

    # Przyszla nowa wiadomosc (href-99), najstarsza wypadla z listy
    await coordinator._attach_message_content([_msg(99)] + [_msg(n) for n in range(4)])

    client.async_get_message_content.assert_awaited_once_with("href-99")
    assert "href-4" not in coordinator._message_content


async def test_blad_pobrania_nie_dodaje_tresci(hass):
    coordinator, client = _coordinator(hass, enabled=True, content=None)
    messages = [_msg(1)]
    await coordinator._attach_message_content(messages)
    assert "content" not in messages[0]
    assert coordinator._message_content == {}


async def test_options_flow_wlacza_pobieranie_tresci(hass):
    from homeassistant.data_entry_flow import FlowResultType
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    from custom_components.librus_apix.const import DOMAIN

    entry = MockConfigEntry(
        domain=DOMAIN, data={"username": "u", "password": "p"}, title="Librus APIX (u)"
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_FETCH_MESSAGE_CONTENT: True}
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert entry.options[CONF_FETCH_MESSAGE_CONTENT] is True
