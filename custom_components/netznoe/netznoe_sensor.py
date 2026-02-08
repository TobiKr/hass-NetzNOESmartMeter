"""Netz NO Smartmeter sensor entity."""
import asyncio
import logging
from datetime import datetime
from typing import Any, Optional

from homeassistant.components.sensor import (
    ENTITY_ID_FORMAT,
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import UnitOfEnergy
from homeassistant.util import slugify

from .AsyncSmartmeter import AsyncSmartmeter
from .api import Smartmeter
from .importer import Importer

_LOGGER = logging.getLogger(__name__)


class NetzNoeSensor(SensorEntity):
    """Netz NO Smartmeter sensor for energy consumption."""

    def __init__(
        self,
        username: str,
        password: str,
        metering_point_id: str,
        account_info: Optional[dict] = None,
        has_ftm_meter_data: bool = True,
    ) -> None:
        """Initialize the sensor.

        Args:
            username: Netz NO username
            password: Netz NO password
            metering_point_id: The metering point ID
            account_info: Optional account information
            has_ftm_meter_data: True for 15-min interval meters, False for daily meters
        """
        super().__init__()
        self.username = username
        self.password = password
        self.metering_point_id = metering_point_id
        self.account_info = account_info or {}
        self.has_ftm_meter_data = has_ftm_meter_data

        # Sensor attributes
        self._attr_native_value: float | None = None
        self._attr_extra_state_attributes = {}
        self._attr_name = f"Smartmeter {metering_point_id}"
        self._attr_icon = "mdi:flash"
        self._attr_state_class = SensorStateClass.TOTAL_INCREASING
        self._attr_device_class = SensorDeviceClass.ENERGY
        self._attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR

        self._available: bool = True
        self._last_update: Optional[str] = None
        self._import_task: asyncio.Task | None = None

    @property
    def get_state(self) -> Optional[str]:
        """Return formatted state value."""
        if self._attr_native_value is not None:
            return f"{self._attr_native_value:.3f}"
        return None

    @property
    def _id(self):
        """Return entity ID."""
        return ENTITY_ID_FORMAT.format(slugify(self._attr_name).lower())

    @property
    def unique_id(self) -> str:
        """Return unique ID for the sensor."""
        return f"netznoe_{self.metering_point_id}"

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._available

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        attrs = self._attr_extra_state_attributes.copy()
        attrs["metering_point_id"] = self.metering_point_id
        attrs["last_update"] = self._last_update
        attrs["has_ftm_meter_data"] = self.has_ftm_meter_data
        return attrs

    async def async_added_to_hass(self) -> None:
        """Run when entity is added to hass."""
        self._import_task = self.hass.async_create_task(
            self._async_background_update()
        )

    async def _async_background_update(self) -> None:
        """Perform the first update as a background task."""
        try:
            await self._async_do_update()
        except Exception as e:
            _LOGGER.exception("Error during background update: %s", e)
        finally:
            self._import_task = None
            self.async_write_ha_state()

    async def async_update(self) -> None:
        """Update sensor state (called by HA polling)."""
        if self._import_task is not None:
            _LOGGER.debug(
                "Import still in progress for %s, skipping periodic update",
                self.metering_point_id,
            )
            return
        await self._async_do_update()

    async def _async_do_update(self) -> None:
        """Perform the actual sensor update."""
        try:
            smartmeter = Smartmeter(username=self.username, password=self.password)
            async_smartmeter = AsyncSmartmeter(self.hass, smartmeter)

            await async_smartmeter.login()
            _LOGGER.debug("Login successful for %s", self.metering_point_id)

            # Get account info
            account_info = await async_smartmeter.get_account_info()
            _LOGGER.debug("Account info: %s", account_info)
            self._attr_extra_state_attributes = account_info

            is_active = async_smartmeter.is_active(account_info)
            _LOGGER.debug("is_active: %s", is_active)

            if is_active:
                # Import historical data for energy dashboard
                importer = Importer(
                    self.hass,
                    async_smartmeter,
                    self.metering_point_id,
                    self.unit_of_measurement,
                    has_ftm_meter_data=self.has_ftm_meter_data,
                )
                cumulative_total = await importer.async_import()

                # Use cumulative total from importer for sensor state
                if cumulative_total is not None:
                    _LOGGER.debug("Cumulative total from importer: %s", cumulative_total)
                    self._attr_native_value = float(cumulative_total)
                else:
                    _LOGGER.debug("No cumulative total available")
            else:
                _LOGGER.warning("Smartmeter %s is not active, skipping data fetch", self.metering_point_id)

            self._available = True
            self._last_update = datetime.now().strftime("%d.%m.%Y %H:%M:%S")

        except TimeoutError as e:
            self._available = False
            _LOGGER.warning("Netz NO API timeout: %s", e)
        except Exception as e:
            self._available = False
            _LOGGER.exception("Error updating Netz NO sensor: %s", e)
