"""Set up the Netz NO Smartmeter integration."""
import logging

from homeassistant import config_entries, core
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.exceptions import ConfigEntryNotReady

from .api import Smartmeter
from .api.errors import SmartmeterConnectionError, SmartmeterLoginError
from .AsyncSmartmeter import AsyncSmartmeter
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["sensor"]


async def async_setup_entry(
    hass: core.HomeAssistant, entry: config_entries.ConfigEntry
) -> bool:
    """Set up platform from a ConfigEntry."""
    hass.data.setdefault(DOMAIN, {})

    # Create a shared API client for all sensors under this config entry
    smartmeter = Smartmeter(
        username=entry.data[CONF_USERNAME],
        password=entry.data[CONF_PASSWORD],
    )
    async_smartmeter = AsyncSmartmeter(hass, smartmeter)

    try:
        await async_smartmeter.login()
    except (SmartmeterConnectionError, SmartmeterLoginError) as err:
        raise ConfigEntryNotReady(f"Cannot connect to Netz NO: {err}") from err

    hass.data[DOMAIN][entry.entry_id] = {
        "config": entry.data,
        "client": async_smartmeter,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(
    hass: core.HomeAssistant, entry: config_entries.ConfigEntry
) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


async def async_migrate_entry(
    hass: core.HomeAssistant, config_entry: config_entries.ConfigEntry
) -> bool:
    """Migrate old config entries to new format."""
    _LOGGER.debug("Migrating from version %s", config_entry.version)

    if config_entry.version == 1:
        new_data = {**config_entry.data}
        new_data.pop("account_info", None)

        hass.config_entries.async_update_entry(
            config_entry, data=new_data, version=2
        )
        _LOGGER.info("Migration to version 2 successful")

    return True
