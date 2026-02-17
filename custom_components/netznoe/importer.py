"""Historical data importer for Netz NO Smartmeter."""
import calendar
import logging
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from operator import itemgetter
from typing import Optional

from homeassistant.components.recorder import get_instance
from homeassistant.components.recorder.models import StatisticData, StatisticMetaData
from homeassistant.components.recorder.statistics import (
    async_add_external_statistics,
    get_last_statistics,
)
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from .AsyncSmartmeter import AsyncSmartmeter
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class Importer:
    """Import historical consumption data into Home Assistant statistics."""

    def __init__(
        self,
        hass: HomeAssistant,
        async_smartmeter: AsyncSmartmeter,
        metering_point_id: str,
        unit_of_measurement: str,
        has_ftm_meter_data: bool = True,
    ):
        """Initialize the importer.

        Args:
            hass: Home Assistant instance
            async_smartmeter: Async smartmeter client
            metering_point_id: Metering point ID
            unit_of_measurement: Unit of measurement for statistics
            has_ftm_meter_data: True for 15-min interval meters, False for daily meters
        """
        self.id = f"{DOMAIN}:{metering_point_id.lower()}"
        self.metering_point_id = metering_point_id
        self.unit_of_measurement = unit_of_measurement
        self.hass = hass
        self.async_smartmeter = async_smartmeter
        self.has_ftm_meter_data = has_ftm_meter_data

    def is_last_inserted_stat_valid(self, last_inserted_stat: dict) -> bool:
        """Check if last inserted statistics are valid."""
        return (
            len(last_inserted_stat) == 1
            and len(last_inserted_stat.get(self.id, [])) == 1
            and "sum" in last_inserted_stat[self.id][0]
            and "end" in last_inserted_stat[self.id][0]
        )

    def prepare_start_off_point(
        self, last_inserted_stat: dict
    ) -> Optional[tuple[datetime, Decimal]]:
        """Prepare starting point for incremental import."""
        _sum = Decimal(last_inserted_stat[self.id][0]["sum"])
        start = last_inserted_stat[self.id][0]["end"]

        # Handle different types returned by HA core
        if isinstance(start, (int, float)):
            start = dt_util.utc_from_timestamp(start)
        if isinstance(start, str):
            start = dt_util.parse_datetime(start)

        if not isinstance(start, datetime):
            _LOGGER.error(
                "Unexpected type for statistics end: %s (type: %s)",
                last_inserted_stat,
                type(last_inserted_stat[self.id][0]["end"]),
            )
            return None

        # Don't query if less than 24h since last update
        min_wait = timedelta(hours=24)
        delta_t = datetime.now(timezone.utc) - start.replace(microsecond=0)
        if delta_t <= min_wait:
            _LOGGER.debug(
                "Skipping API query - last update is recent. Next update in %s",
                min_wait - delta_t,
            )
            return None

        return start, _sum

    async def async_import(self) -> Optional[Decimal]:
        """Import historical data.

        Returns:
            The cumulative total usage after import, or None if import was skipped.
        """
        # Query last statistics
        last_inserted_stat = await get_instance(self.hass).async_add_executor_job(
            get_last_statistics,
            self.hass,
            1,
            self.id,
            True,
            {"sum", "state"},
        )
        _LOGGER.debug("Last inserted stat: %s", last_inserted_stat)

        try:
            if not self.is_last_inserted_stat_valid(last_inserted_stat):
                # Initial import - last 3 years
                _LOGGER.warning(
                    "Starting initial import. This may take some time."
                )
                return await self._initial_import_statistics()
            else:
                # Incremental import
                start_off_point = self.prepare_start_off_point(last_inserted_stat)
                if start_off_point is None:
                    # Return existing sum if no new import needed
                    return Decimal(last_inserted_stat[self.id][0]["sum"])
                start, _sum = start_off_point
                return await self._incremental_import_statistics(start, _sum)

        except TimeoutError as e:
            _LOGGER.warning("Timeout during import: %s", e)
            return None
        except Exception as e:
            _LOGGER.exception("Error during import: %s", e)
            return None

    def get_statistics_metadata(self) -> StatisticMetaData:
        """Get statistics metadata."""
        return StatisticMetaData(
            source=DOMAIN,
            statistic_id=self.id,
            name=f"Netz NO {self.metering_point_id}",
            unit_of_measurement=self.unit_of_measurement,
            has_mean=False,
            has_sum=True,
        )

    async def _initial_import_statistics(self) -> Decimal:
        """Perform initial import of statistics."""
        return await self._import_statistics()

    async def _incremental_import_statistics(
        self, start: datetime, total_usage: Decimal
    ) -> Decimal:
        """Perform incremental import of statistics."""
        return await self._import_statistics(start=start, total_usage=total_usage)

    async def _import_statistics(
        self,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        total_usage: Decimal = Decimal(0),
    ) -> Decimal:
        """Import statistics from Netz NO API.

        Dispatches to the appropriate import method based on meter type.
        """
        now = datetime.now(timezone.utc)

        if start is None:
            # Default: 3 years of history
            start = now - timedelta(days=365 * 3)
        if end is None:
            end = now

        if start.tzinfo is None:
            raise ValueError("start datetime must be timezone-aware!")

        _LOGGER.debug(
            "Importing data from %s to %s (FTM: %s)", start, end, self.has_ftm_meter_data
        )
        if start > end:
            _LOGGER.warning("Start date is after end date, skipping")
            return total_usage

        if self.has_ftm_meter_data:
            return await self._import_ftm_statistics(start, end, total_usage)
        else:
            return await self._import_daily_statistics(start, end, total_usage)

    async def _import_ftm_statistics(
        self,
        start: datetime,
        end: datetime,
        total_usage: Decimal,
    ) -> Decimal:
        """Import FTM (15-minute interval) statistics.

        Each day returns individual readings (e.g., 96 values for 15-min intervals).
        We aggregate to hourly statistics (HA requires timestamps at top of hour).
        """
        hourly_readings = defaultdict(Decimal)
        current_date = start.date()
        end_date = end.date()

        while current_date <= end_date:
            try:
                times, values = await self.async_smartmeter.get_consumption_day(
                    current_date, self.metering_point_id
                )

                if values:
                    # Calculate interval based on number of readings
                    # e.g., 96 values = 15 min, 24 values = 60 min, 1 value = 1440 min
                    interval_minutes = (24 * 60) // len(values) if len(values) > 0 else 1440

                    # Create a datetime for the start of the day
                    day_start = datetime.combine(
                        current_date, datetime.min.time(), tzinfo=timezone.utc
                    )

                    # Aggregate readings to hourly buckets
                    for i, value in enumerate(values):
                        if value is not None:
                            reading_time = day_start + timedelta(minutes=i * interval_minutes)
                            # Round down to the start of the hour
                            hour_start = reading_time.replace(minute=0, second=0, microsecond=0)
                            # Skip hours already imported (start = end of last stat)
                            if hour_start < start:
                                continue
                            hourly_readings[hour_start] += Decimal(str(value))

            except Exception as e:
                _LOGGER.debug("Could not fetch data for %s: %s", current_date, e)

            current_date += timedelta(days=1)

        # Build statistics with hourly resolution
        statistics = []
        metadata = self.get_statistics_metadata()

        for ts, usage in sorted(hourly_readings.items(), key=itemgetter(0)):
            total_usage += usage
            statistics.append(
                StatisticData(start=ts, sum=float(total_usage), state=float(usage))
            )

        if statistics:
            _LOGGER.debug(
                "Importing %d FTM statistics entries from %s to %s",
                len(statistics),
                statistics[0]["start"],
                statistics[-1]["start"],
            )
            async_add_external_statistics(self.hass, metadata, statistics)

        return total_usage

    async def _import_daily_statistics(
        self,
        start: datetime,
        end: datetime,
        total_usage: Decimal,
    ) -> Decimal:
        """Import daily meter statistics using the Month endpoint.

        Each day's single consumption value becomes one statistics entry
        assigned to midnight UTC of that day.
        """
        daily_readings: dict[datetime, Decimal] = {}
        start_date = start.date()
        end_date = end.date()

        # Iterate month by month
        current_year = start_date.year
        current_month = start_date.month

        while date(current_year, current_month, 1) <= end_date:
            try:
                times, values = await self.async_smartmeter.get_consumption_month(
                    current_year, current_month, self.metering_point_id
                )

                if values:
                    days_in_month = calendar.monthrange(current_year, current_month)[1]
                    for day_index, value in enumerate(values):
                        if value is None:
                            continue
                        day_num = day_index + 1  # 1-based day of month
                        if day_num > days_in_month:
                            break
                        day_date = date(current_year, current_month, day_num)
                        # Skip days outside our requested range.
                        # Use <= for start_date because incremental imports set start
                        # to the END of the last stat (midnight + 1hr), so start_date
                        # equals the last already-imported day — skip it to avoid
                        # re-adding its value to the cumulative sum.
                        if day_date <= start_date or day_date > end_date:
                            continue
                        day_midnight = datetime.combine(
                            day_date, datetime.min.time(), tzinfo=timezone.utc
                        )
                        daily_readings[day_midnight] = Decimal(str(value))

            except Exception as e:
                _LOGGER.debug(
                    "Could not fetch monthly data for %d-%02d: %s",
                    current_year, current_month, e
                )

            # Advance to next month
            if current_month == 12:
                current_year += 1
                current_month = 1
            else:
                current_month += 1

        # Build statistics with daily resolution
        statistics = []
        metadata = self.get_statistics_metadata()

        for ts, usage in sorted(daily_readings.items(), key=itemgetter(0)):
            total_usage += usage
            statistics.append(
                StatisticData(start=ts, sum=float(total_usage), state=float(usage))
            )

        if statistics:
            _LOGGER.debug(
                "Importing %d daily statistics entries from %s to %s",
                len(statistics),
                statistics[0]["start"],
                statistics[-1]["start"],
            )
            async_add_external_statistics(self.hass, metadata, statistics)

        return total_usage
