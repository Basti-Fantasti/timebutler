"""Tests for the Timebutler config flow."""
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResultType

from custom_components.timebutler.api import TimebutlerAuthError, TimebutlerConnectionError
from custom_components.timebutler.const import (
    CONF_API_TOKEN,
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MAX_SCAN_INTERVAL,
    MIN_SCAN_INTERVAL,
)

MOCK_TOKEN = "test_api_token_12345678"


def _mock_client(valid: bool = True, side_effect=None):
    """Return a patched TimebutlerApiClient for config flow."""
    mock = AsyncMock()
    if side_effect:
        mock.async_validate_token.side_effect = side_effect
    else:
        mock.async_validate_token.return_value = valid
    return mock


async def test_form_shows_on_init(hass):
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}


async def test_successful_setup_creates_entry(hass):
    with patch(
        "custom_components.timebutler.config_flow.TimebutlerApiClient",
        return_value=_mock_client(valid=True),
    ), patch("custom_components.timebutler.async_setup_entry", return_value=True):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_API_TOKEN: MOCK_TOKEN}
        )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "Timebutler"
    assert result["data"][CONF_API_TOKEN] == MOCK_TOKEN
    assert result["options"][CONF_SCAN_INTERVAL] == DEFAULT_SCAN_INTERVAL


async def test_invalid_token_shows_error(hass):
    with patch(
        "custom_components.timebutler.config_flow.TimebutlerApiClient",
        return_value=_mock_client(side_effect=TimebutlerAuthError("invalid")),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_API_TOKEN: MOCK_TOKEN}
        )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"]["base"] == "invalid_auth"


async def test_connection_error_shows_error(hass):
    with patch(
        "custom_components.timebutler.config_flow.TimebutlerApiClient",
        return_value=_mock_client(side_effect=TimebutlerConnectionError("timeout")),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_API_TOKEN: MOCK_TOKEN}
        )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"]["base"] == "cannot_connect"


async def test_duplicate_entry_aborted(hass):
    with patch(
        "custom_components.timebutler.config_flow.TimebutlerApiClient",
        return_value=_mock_client(valid=True),
    ), patch("custom_components.timebutler.async_setup_entry", return_value=True):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_API_TOKEN: MOCK_TOKEN}
        )

        # With single_config_entry=true, second init is aborted immediately
        result2 = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

    assert result2["type"] == FlowResultType.ABORT


async def test_options_flow_updates_scan_interval(hass):
    with patch(
        "custom_components.timebutler.config_flow.TimebutlerApiClient",
        return_value=_mock_client(valid=True),
    ), patch("custom_components.timebutler.async_setup_entry", return_value=True):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_API_TOKEN: MOCK_TOKEN}
        )

    entry = hass.config_entries.async_entries(DOMAIN)[0]
    new_interval = MIN_SCAN_INTERVAL * 2

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] == FlowResultType.FORM

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_SCAN_INTERVAL: new_interval}
    )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert entry.options[CONF_SCAN_INTERVAL] == new_interval
