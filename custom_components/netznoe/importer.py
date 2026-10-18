"""Historical data importer for Netz NO Smartmeter."""
import calendar
import logging
from collections import defaultdict
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from operator import itemgetter
from typing import Optional

from homeassistant.components.recorder import get_instance
from homeassistant.components.recorder.models import (
    StatisticData,
    StatisticMeanType,
    StatisticMetaData,
)
from homeassistant.components.recorder.statistics import (
    async_add_external_statistics,
    get_last_statistics,
    statistics_during_period,
)
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util
from homeassistant.util.unit_conversion import EnergyConverter

from .api.client import ConsumptionData
from .AsyncSmartmeter import AsyncSmartmeter
from .const import DEFAULT_REIMPORT_DAYS, DOMAIN

_LOGGER = logging.getLogger(__name__)


def _to_datetime(value) -> Optional[datetime]:
    """Convert a statistics timestamp as returned by HA core to a datetime."""
    if isinstance(value, (int, float)):
        return dt_util.utc_from_timestamp(value)
    if isinstance(value, str):
        return dt_util.parse_datetime(value)
    if isinstance(value, datetime):
        return value
    return None


class Importer:
    """Import historical consumption data into Home Assistant statistics."""

    def __init__(
        self,
        hass: HomeAssistant,
        async_smartmeter: AsyncSmartmeter,
        metering_point_id: str,
        unit_of_measurement: str,
        has_ftm_meter_data: bool = True,
        import_estimated_values: bool = False,
        reimport_days: int = DEFAULT_REIMPORT_DAYS,
    ):
        """Initialize the importer.

        Args:
            hass: Home Assistant instance
            async_smartmeter: Async smartmeter client
            metering_point_id: Metering point ID
            unit_of_measurement: Unit of measurement for statistics
            has_ftm_meter_data: True for 15-min interval meters, False for daily meters
            import_estimated_values: Use estimated values where no measured value
                is available (yet)
            reimport_days: Number of past days to fetch and rewrite on every
                incremental import, so that late or corrected values are picked up.
                0 only imports data newer than the last statistic.
        """
        self.id = f"{DOMAIN}:{metering_point_id.lower()}"
        self.metering_point_id = metering_point_id
        self.unit_of_measurement = unit_of_measurement
        self.hass = hass
        self.async_smartmeter = async_smartmeter
        self.has_ftm_meter_data = has_ftm_meter_data
        self.import_estimated_values = import_estimated_values
        self.reimport_days = reimport_days

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
        start = _to_datetime(last_inserted_stat[self.id][0]["end"])

        if not isinstance(start, datetime):
            _LOGGER.error(
                "Unexpected type for statistics end: %s (type: %s)",
                last_inserted_stat,
                type(last_inserted_stat[self.id][0]["end"]),
            )
            return None

        # Don't query if less than 1h since last update
        min_wait = timedelta(hours=1)
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
            unit_class=EnergyConverter.UNIT_CLASS,
            mean_type=StatisticMeanType.NONE,
            has_sum=True,
        )

    async def _initial_import_statistics(self) -> Decimal:
        """Perform initial import of statistics."""
        return await self._import_statistics()

    async def _incremental_import_statistics(
        self, start: datetime, total_usage: Decimal
    ) -> Decimal:
        """Perform incremental import of statistics.

        Instead of resuming right at the end of the last statistic, rewind to
        the start of the re-import window (if that is earlier) and rewrite
        everything from there. This fills hours whose values arrived late and
        replaces estimates once measured values become available.
        """
        existing: dict[datetime, Decimal] = {}
        window = await self._get_reimport_window(start)
        if window is not None:
            start, total_usage, existing = window
        return await self._import_statistics(
            start=start, total_usage=total_usage, existing=existing
        )

    async def _get_reimport_window(
        self, last_end: datetime
    ) -> Optional[tuple[datetime, Decimal, dict[datetime, Decimal]]]:
        """Determine the re-import window for an incremental import.

        Returns:
            The window start, the cumulative sum right before it and the
            already stored usage per hour within the window, or None if the
            import should simply resume at the end of the last statistic.
        """
        if self.reimport_days <= 0:
            return None

        # Midnight UTC, which is a valid start for both hourly and daily statistics.
        window_start = datetime.combine(
            (datetime.now(timezone.utc) - timedelta(days=self.reimport_days)).date(),
            time.min,
            tzinfo=timezone.utc,
        )
        if window_start >= last_end:
            return None

        stats = await get_instance(self.hass).async_add_executor_job(
            statistics_during_period,
            self.hass,
            window_start,
            None,
            {self.id},
            "hour",
            None,
            {"sum", "state"},
        )
        rows = stats.get(self.id, [])
        if not rows:
            return None

        existing: dict[datetime, Decimal] = {}
        for row in rows:
            row_start = _to_datetime(row.get("start"))
            if row_start is None or row.get("sum") is None or row.get("state") is None:
                _LOGGER.debug("Unexpected statistics row %s, not re-importing", row)
                return None
            existing[row_start] = Decimal(str(row["state"]))

        # Each row's state is that hour's usage, so the cumulative sum before
        # the window is the first row's sum minus its own usage. Hours without
        # a row (gaps) contributed nothing to the sum, so this also holds if
        # the window starts in a gap.
        first = rows[0]
        base_sum = Decimal(str(first["sum"])) - Decimal(str(first["state"]))

        _LOGGER.debug(
            "Re-importing from %s (last statistic ended %s, sum before window %s)",
            window_start,
            last_end,
            base_sum,
        )
        return window_start, base_sum, existing

    def _pick_value(self, data: ConsumptionData, index: int) -> tuple[Optional[float], bool]:
        """Return the value for a slot and whether it is an estimate.

        The measured value always wins. The estimate is only used if enabled
        and no measured value is available.
        """
        if index < len(data.metered) and data.metered[index] is not None:
            return data.metered[index], False
        if (
            self.import_estimated_values
            and index < len(data.estimated)
            and data.estimated[index] is not None
        ):
            return data.estimated[index], True
        return None, False

    async def _import_statistics(
        self,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        total_usage: Decimal = Decimal(0),
        existing: Optional[dict[datetime, Decimal]] = None,
    ) -> Decimal:
        """Import statistics from Netz NO API.

        Dispatches to the appropriate import method based on meter type.

        Args:
            start: Import data from this point in time on
            end: Import data up to this point in time
            total_usage: Cumulative sum right before start
            existing: Usage of statistics already stored at or after start,
                which are rewritten by this import
        """
        now = datetime.now(timezone.utc)

        if start is None:
            # Default: 3 years of history
            start = now - timedelta(days=365 * 3)
        if end is None:
            end = now
        if existing is None:
            existing = {}

        if start.tzinfo is None:
            raise ValueError("start datetime must be timezone-aware!")

        _LOGGER.debug(
            "Importing data from %s to %s (FTM: %s)", start, end, self.has_ftm_meter_data
        )
        if start > end:
            _LOGGER.warning("Start date is after end date, skipping")
            return total_usage

        if self.has_ftm_meter_data:
            readings = await self._fetch_ftm_readings(start, end)
        else:
            readings = await self._fetch_daily_readings(start, end)

        # Statistics already stored within the window are rewritten as well,
        # so that no later row keeps a stale cumulative sum. Where the API
        # delivered no value this time (e.g. a failed request), the stored
        # value is kept.
        for ts, usage in existing.items():
            readings.setdefault(ts, usage)

        return self._write_statistics(readings, total_usage)

    async def _fetch_ftm_readings(
        self,
        start: datetime,
        end: datetime,
    ) -> dict[datetime, Decimal]:
        """Fetch FTM (15-minute interval) readings, aggregated per hour.

        Each day returns individual readings (e.g., 96 values for 15-min intervals)
        together with the timestamp of each one. We aggregate to hourly statistics
        (HA requires timestamps at top of hour).

        The API's timestamps carry no UTC offset but are UTC, and each marks the
        *end* of its interval. A day's readings therefore run from 22:15 on the
        previous day through 22:00 on the day itself.
        """
        hourly_readings: dict[datetime, Decimal] = defaultdict(Decimal)
        estimated_count = 0
        current_date = start.date()
        end_date = end.date()

        while current_date <= end_date:
            try:
                data = await self.async_smartmeter.get_consumption_day_detailed(
                    current_date, self.metering_point_id
                )
                times = data.times
                value_count = max(len(data.metered), len(data.estimated))

                if len(times) < value_count:
                    _LOGGER.warning(
                        "Netz NO returned %d values but only %d timestamps for %s, "
                        "skipping the surplus readings",
                        value_count,
                        len(times),
                        current_date,
                    )

                # Aggregate readings to hourly buckets, using the timestamp
                # the API reports for each reading rather than assuming the
                # day starts at midnight UTC.
                for i, time_str in enumerate(times):
                    reading_time = dt_util.parse_datetime(time_str) if time_str else None
                    if reading_time is None:
                        continue
                    if reading_time.tzinfo is None:
                        # The timestamps carry no offset and are UTC.
                        reading_time = reading_time.replace(tzinfo=timezone.utc)

                    # The timestamp is the end of the interval, so step back
                    # a minute before rounding down: a reading stamped 23:00
                    # covers 22:45-23:00 and belongs to the 22:00 hour.
                    hour_start = (reading_time - timedelta(minutes=1)).replace(
                        minute=0, second=0, microsecond=0
                    )
                    # Skip hours already imported (start = end of last stat)
                    if hour_start < start:
                        continue

                    value, is_estimate = self._pick_value(data, i)
                    if value is None:
                        continue
                    if is_estimate:
                        estimated_count += 1
                    hourly_readings[hour_start] += Decimal(str(value))

            except Exception as e:
                _LOGGER.debug("Could not fetch data for %s: %s", current_date, e)

            current_date += timedelta(days=1)

        if estimated_count:
            _LOGGER.debug(
                "Using %d estimated readings where no measured values are available",
                estimated_count,
            )

        return hourly_readings

    async def _fetch_daily_readings(
        self,
        start: datetime,
        end: datetime,
    ) -> dict[datetime, Decimal]:
        """Fetch daily meter readings using the Month endpoint.

        Each day's single consumption value becomes one statistics entry
        assigned to midnight UTC of that day.
        """
        daily_readings: dict[datetime, Decimal] = {}
        estimated_count = 0
        start_date = start.date()
        end_date = end.date()

        # Iterate month by month
        current_year = start_date.year
        current_month = start_date.month

        while date(current_year, current_month, 1) <= end_date:
            try:
                data = await self.async_smartmeter.get_consumption_month_detailed(
                    current_year, current_month, self.metering_point_id
                )

                days_in_month = calendar.monthrange(current_year, current_month)[1]
                value_count = max(len(data.metered), len(data.estimated))
                for day_index in range(min(value_count, days_in_month)):
                    day_num = day_index + 1  # 1-based day of month
                    day_date = date(current_year, current_month, day_num)
                    day_midnight = datetime.combine(
                        day_date, datetime.min.time(), tzinfo=timezone.utc
                    )
                    # Skip days outside our requested range. Incremental
                    # imports set start to the END of the last stat
                    # (midnight + 1hr), so the last already-imported day is
                    # skipped to avoid re-adding its value to the sum.
                    if day_midnight < start or day_date > end_date:
                        continue

                    value, is_estimate = self._pick_value(data, day_index)
                    if value is None:
                        continue
                    if is_estimate:
                        estimated_count += 1
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

        if estimated_count:
            _LOGGER.debug(
                "Using %d estimated daily values where no measured values are available",
                estimated_count,
            )

        return daily_readings

    def _write_statistics(
        self, readings: dict[datetime, Decimal], total_usage: Decimal
    ) -> Decimal:
        """Write readings as statistics, accumulating the sum from total_usage."""
        statistics = []
        metadata = self.get_statistics_metadata()

        for ts, usage in sorted(readings.items(), key=itemgetter(0)):
            total_usage += usage
            statistics.append(
                StatisticData(start=ts, sum=float(total_usage), state=float(usage))
            )

        if statistics:
            _LOGGER.debug(
                "Importing %d statistics entries from %s to %s",
                len(statistics),
                statistics[0]["start"],
                statistics[-1]["start"],
            )
            async_add_external_statistics(self.hass, metadata, statistics)

        return total_usage
