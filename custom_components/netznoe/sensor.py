"""Netz NO Smartmeter sensor platform."""
import collections.abc
from datetime import timedelta
from typing import Optional

import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant import config_entries, core
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import CONF_DEVICE_ID, CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import CONF_METERING_POINTS, DOMAIN
from .netznoe_sensor import NetzNoeSensor

# Time between updating data from Netz NO (every hour)
SCAN_INTERVAL = timedelta(hours=1)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Required(CONF_DEVICE_ID): cv.string,
    }
)


async def async_setup_entry(
    hass: core.HomeAssistant,
    config_entry: config_entries.ConfigEntry,
    async_add_entities,
):
    """Set up sensors from a config entry created in the integrations UI."""
    config = hass.data[DOMAIN][config_entry.entry_id]
    account_info = config.get("account_info", {})

    sensors = [
        NetzNoeSensor(
            config[CONF_USERNAME],
            config[CONF_PASSWORD],
            mp["meteringPointId"],
            account_info,
            has_ftm_meter_data=mp.get("hasFtmMeterData", True),
        )
        for mp in config.get(CONF_METERING_POINTS, [])
    ]
    async_add_entities(sensors, update_before_add=False)


async def async_setup_platform(
    hass: core.HomeAssistant,
    config: ConfigType,
    async_add_entities: collections.abc.Callable,
    discovery_info: Optional[DiscoveryInfoType] = None,
) -> None:
    """Set up the sensor platform via configuration.yaml."""
    sensor = NetzNoeSensor(
        config[CONF_USERNAME], config[CONF_PASSWORD], config[CONF_DEVICE_ID]
    )
    async_add_entities([sensor], update_before_add=False)
