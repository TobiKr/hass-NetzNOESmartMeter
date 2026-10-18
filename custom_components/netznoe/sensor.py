"""Netz NO Smartmeter sensor platform."""
from datetime import timedelta

from homeassistant import config_entries, core

from .const import (
    CONF_IMPORT_ESTIMATED_VALUES,
    CONF_METERING_POINTS,
    CONF_REIMPORT_DAYS,
    DEFAULT_IMPORT_ESTIMATED_VALUES,
    DEFAULT_REIMPORT_DAYS,
    DOMAIN,
)
from .netznoe_sensor import NetzNoeSensor

# Time between updating data from Netz NO (every hour)
SCAN_INTERVAL = timedelta(hours=1)


async def async_setup_entry(
    hass: core.HomeAssistant,
    config_entry: config_entries.ConfigEntry,
    async_add_entities,
):
    """Set up sensors from a config entry created in the integrations UI."""
    entry_data = hass.data[DOMAIN][config_entry.entry_id]
    async_smartmeter = entry_data["client"]
    config = entry_data["config"]

    import_estimated_values = config_entry.options.get(
        CONF_IMPORT_ESTIMATED_VALUES, DEFAULT_IMPORT_ESTIMATED_VALUES
    )
    reimport_days = config_entry.options.get(CONF_REIMPORT_DAYS, DEFAULT_REIMPORT_DAYS)

    sensors = [
        NetzNoeSensor(
            async_smartmeter,
            mp,
            import_estimated_values=import_estimated_values,
            reimport_days=reimport_days,
        )
        for mp in config.get(CONF_METERING_POINTS, [])
    ]
    async_add_entities(sensors, update_before_add=False)
