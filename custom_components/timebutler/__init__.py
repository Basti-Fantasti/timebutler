"""The Timebutler integration."""

from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import TimebutlerApiClient, TimebutlerAuthError
from .const import CONF_API_TOKEN, CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL, DOMAIN
from .coordinator import TimebutlerDataUpdateCoordinator
from .util import unique_id_from_token

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Timebutler from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    # Get configuration
    api_token = entry.data[CONF_API_TOKEN]
    scan_interval = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)

    # Create API client
    session = async_get_clientsession(hass)
    client = TimebutlerApiClient(api_token, session)

    # Validate token
    try:
        valid = await client.async_validate_token()
        if not valid:
            raise ConfigEntryAuthFailed("Invalid API token")
    except TimebutlerAuthError as err:
        raise ConfigEntryAuthFailed("Invalid API token") from err

    # Create coordinator
    coordinator = TimebutlerDataUpdateCoordinator(
        hass,
        client,
        timedelta(seconds=scan_interval),
    )

    # Fetch initial data
    await coordinator.async_config_entry_first_refresh()

    # Store coordinator
    hass.data[DOMAIN][entry.entry_id] = coordinator

    # Set up platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Register options update listener
    entry.async_on_unload(entry.add_update_listener(async_options_update_listener))

    return True


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate an old config entry."""
    if entry.version > 1:
        # Downgrade from a future version is not supported
        return False

    if entry.minor_version < 2:
        # Replace the token prefix unique ID with a hash of the token
        hass.config_entries.async_update_entry(
            entry,
            unique_id=unique_id_from_token(entry.data[CONF_API_TOKEN]),
            minor_version=2,
        )
        _LOGGER.debug("Migrated config entry to version 1.2")

    return True


async def async_options_update_listener(
    hass: HomeAssistant, entry: ConfigEntry
) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)

    return unload_ok
