"""Async wrapper for Netz NO Smartmeter API."""
import asyncio
import logging
from datetime import date
from typing import List, Optional, Tuple

from homeassistant.core import HomeAssistant

from .api import Smartmeter
from .utils import before, today

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

    async def login(self) -> None:
        """Async login to Netz NO API."""
        async with self.login_lock:
            await self.hass.async_add_executor_job(self.smartmeter.login)

    async def ensure_logged_in(self) -> None:
        """Ensure the client is logged in, re-authenticating if needed."""
        if not self.smartmeter.is_logged_in():
            await self.login()

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
        self, meter_id: Optional[str] = None, has_ftm_meter_data: bool = True
    ) -> Optional[float]:
        """Get the latest meter reading.

        For FTM meters: tries yesterday first, then day before yesterday.
        For daily meters: fetches current month and returns last non-null value.
        Returns consumption in kWh.
        """
        if has_ftm_meter_data:
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
        else:
            # Daily meter: fetch current month and return last non-null value
            today_date = date.today()
            try:
                times, values = await self.get_consumption_month(
                    today_date.year, today_date.month, meter_id
                )
                if values:
                    for v in reversed(values):
                        if v is not None:
                            _LOGGER.debug("Latest daily reading (kWh): %s", v)
                            return v
            except Exception as e:
                _LOGGER.warning("Could not get monthly reading: %s", e)
        return None
