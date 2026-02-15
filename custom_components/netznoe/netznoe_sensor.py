"""Netz NO Smartmeter sensor entity."""
import asyncio
import logging
from datetime import datetime
from typing import Any, Optional

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import UnitOfEnergy
from homeassistant.helpers.entity import DeviceInfo

from .AsyncSmartmeter import AsyncSmartmeter
from .const import DOMAIN, is_meter_active
from .importer import Importer

_LOGGER = logging.getLogger(__name__)


class NetzNoeSensor(SensorEntity):
    """Netz NO Smartmeter sensor for energy consumption."""

    def __init__(
        self,
        async_smartmeter: AsyncSmartmeter,
        metering_point_data: dict,
    ) -> None:
        """Initialize the sensor.

        Args:
            async_smartmeter: Shared async smartmeter client
            metering_point_data: Full metering point dict from the API
        """
        super().__init__()
        self.async_smartmeter = async_smartmeter
        self.metering_point_id: str = metering_point_data["meteringPointId"]
        self.has_ftm_meter_data: bool = metering_point_data.get("hasFtmMeterData", True)
        self._is_meter_active: bool = is_meter_active(metering_point_data)
        self._smart_meter_type: Optional[str] = metering_point_data.get("smartMeterType")

        # Sensor attributes
        self._attr_native_value: float | None = None
        self._attr_extra_state_attributes = {}
        self._attr_name = f"Smartmeter {self.metering_point_id}"
        self._attr_icon = "mdi:flash"
        self._attr_state_class = SensorStateClass.TOTAL_INCREASING
        self._attr_device_class = SensorDeviceClass.ENERGY
        self._attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR

        self._available: bool = True
        self._last_update: Optional[str] = None
        self._import_task: asyncio.Task | None = None

    @property
    def unique_id(self) -> str:
        """Return unique ID for the sensor."""
        return f"netznoe_{self.metering_point_id}"

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._available

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info for this metering point."""
        return DeviceInfo(
            identifiers={(DOMAIN, self.metering_point_id)},
            name=f"Smartmeter {self.metering_point_id}",
            manufacturer="Netz Niederösterreich",
            model=self._smart_meter_type or "Smartmeter",
        )

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
            # Ensure shared client is logged in (handles session expiry)
            await self.async_smartmeter.ensure_logged_in()
            _LOGGER.debug("Login ensured for %s", self.metering_point_id)

            if not self._is_meter_active:
                _LOGGER.warning(
                    "Smartmeter %s is not active, skipping data fetch",
                    self.metering_point_id,
                )
                return

            # Import historical data for energy dashboard
            importer = Importer(
                self.hass,
                self.async_smartmeter,
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

            self._available = True
            self._last_update = datetime.now().strftime("%d.%m.%Y %H:%M:%S")

        except TimeoutError as e:
            self._available = False
            _LOGGER.warning("Netz NO API timeout: %s", e)
        except Exception as e:
            self._available = False
            _LOGGER.exception("Error updating Netz NO sensor: %s", e)
