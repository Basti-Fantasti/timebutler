"""Config flow for Timebutler integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import TimebutlerApiClient, TimebutlerAuthError, TimebutlerConnectionError
from .const import (
    CONF_API_TOKEN,
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MAX_SCAN_INTERVAL,
    MIN_SCAN_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_API_TOKEN): str,
    }
)


class TimebutlerConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Timebutler."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Validate API token
            session = async_get_clientsession(self.hass)
            client = TimebutlerApiClient(user_input[CONF_API_TOKEN], session)

            try:
                valid = await client.async_validate_token()
                if not valid:
                    errors["base"] = "invalid_auth"
            except TimebutlerAuthError:
                errors["base"] = "invalid_auth"
            except TimebutlerConnectionError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected error during configuration")
                errors["base"] = "unknown"

            if not errors:
                # Prevent duplicate entries
                await self.async_set_unique_id(user_input[CONF_API_TOKEN][:16])
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title="Timebutler",
                    data=user_input,
                    options={CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL},
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Get the options flow for this handler."""
        return TimebutlerOptionsFlowHandler()


class TimebutlerOptionsFlowHandler(OptionsFlow):
    """Handle options flow for Timebutler."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current_interval = self.config_entry.options.get(
            CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
        )

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_SCAN_INTERVAL,
                        default=current_interval,
                    ): vol.All(
                        vol.Coerce(int),
                        vol.Range(min=MIN_SCAN_INTERVAL, max=MAX_SCAN_INTERVAL),
                    ),
                }
            ),
        )
