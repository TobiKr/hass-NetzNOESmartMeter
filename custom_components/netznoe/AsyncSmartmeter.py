"""Async wrapper for Netz NO Smartmeter API."""
import asyncio
import logging
from asyncio import Future
from datetime import date
from typing import Any, Dict, List, Optional, Tuple

from homeassistant.core import HomeAssistant

from .api import Smartmeter
from .const import ATTRS_ACCOUNT_INFO, ATTRS_METERING_POINT
from .utils import translate_dict, before, today

_LOGGER = logging.getLogger(__name__)


class AsyncSmartmeter:
    """Async wrapper for Netz NO Smartmeter synchronous API."""

    def __init__(self, hass: HomeAssistant, smartmeter: Smartmeter):
        """Initialize the async wrapper.

        Args:
            hass: Home Assistant instance
            smartmeter: Smartmeter client instance
        """
        self.hass = hass
        self.smartmeter = smartmeter
        self.login_lock = asyncio.Lock()

    async def login(self) -> Future:
        """Async login to Netz NO API."""
        async with self.login_lock:
            return await self.hass.async_add_executor_job(self.smartmeter.login)

    async def get_account_info(self) -> Dict[str, Any]:
        """Get account information asynchronously."""
        info = await self.hass.async_add_executor_job(self.smartmeter.get_account_info)
        return translate_dict(info, ATTRS_ACCOUNT_INFO)

    async def get_metering_points(self) -> List[Dict[str, Any]]:
        """Get all metering points asynchronously."""
        points = await self.hass.async_add_executor_job(
            self.smartmeter.get_metering_points
        )
        return [translate_dict(p, ATTRS_METERING_POINT) for p in points]

    async def get_consumption_day(
        self, day: date, meter_id: Optional[str] = None
    ) -> Tuple[List[str], List[float]]:
        """Get daily consumption data asynchronously."""
        return await self.hass.async_add_executor_job(
            self.smartmeter.get_consumption_day, day, meter_id
        )

    async def get_consumption_month(
        self, year: int, month: int, meter_id: Optional[str] = None
    ) -> Tuple[List[str], List[float]]:
        """Get monthly consumption data asynchronously."""
        return await self.hass.async_add_executor_job(
            self.smartmeter.get_consumption_month, year, month, meter_id
        )

    async def get_consumption_year(
        self, year: int, meter_id: Optional[str] = None
    ) -> Tuple[List[str], List[float]]:
        """Get yearly consumption data asynchronously."""
        return await self.hass.async_add_executor_job(
            self.smartmeter.get_consumption_year, year, meter_id
        )

    async def get_latest_meter_reading(
        self, meter_id: Optional[str] = None
    ) -> Optional[float]:
        """Get the latest meter reading.

        Tries yesterday first, then day before yesterday.
        Returns consumption sum in kWh.
        """
        for days_ago in [1, 2]:
            try:
                day = before(today(), days_ago).date()
                _LOGGER.debug("Fetching consumption for day: %s, meter: %s", day, meter_id)
                times, values = await self.get_consumption_day(day, meter_id)
                _LOGGER.debug("Consumption response - times: %s, values: %s", times, values)
                if values:
                    # Sum all metered values for the day (values are already in kWh)
                    total = sum(v for v in values if v is not None)
                    _LOGGER.debug("Daily total (kWh): %s", total)
                    return total
            except Exception as e:
                _LOGGER.warning("Could not get reading for %s days ago: %s", days_ago, e)
        return None

    @staticmethod
    def is_active(account_info: Dict[str, Any]) -> bool:
        """Check if the smart meter is active based on account info."""
        return account_info.get("hasActive", False) and account_info.get(
            "hasSmartMeter", False
        )
