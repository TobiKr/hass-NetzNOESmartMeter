"""Netz NO Smartmeter API Client."""
import logging
from datetime import date, timedelta
from typing import Any, Dict, List, Optional, Tuple
from urllib import parse

import requests

from . import constants as const
from .errors import (
    SmartmeterConnectionError,
    SmartmeterLoginError,
    SmartmeterQueryError,
)

logger = logging.getLogger(__name__)


class Smartmeter:
    """Netz NO Smartmeter client."""

    def __init__(self, username: str, password: str):
        """Initialize the Smartmeter API client.

        Args:
            username: Username for Netz NO portal
            password: Password for Netz NO portal
        """
        self.username = username
        self.password = password
        self.session = requests.Session()
        self._is_authenticated = False

        # Account info from API
        self._account_id: Optional[str] = None
        self._metering_point_id: Optional[str] = None
        self._has_smart_meter: bool = False
        self._has_communicative: bool = False
        self._has_active: bool = False
        self._metering_points_cache: List[Dict[str, Any]] = []

    def reset(self):
        """Reset session and authentication state."""
        self.session = requests.Session()
        self._is_authenticated = False
        self._account_id = None
        self._metering_point_id = None
        self._metering_points_cache = []

    def is_logged_in(self) -> bool:
        """Check if user is currently logged in."""
        return self._is_authenticated

    def _validate_session(self) -> bool:
        """Validate if current session is still valid."""
        if not self._is_authenticated:
            return False
        try:
            response = self.session.get(
                parse.urljoin(const.BASE_URL, const.ENDPOINT_USER_INFO)
            )
            return response.status_code == 200
        except requests.exceptions.RequestException:
            return False

    def login(self) -> "Smartmeter":
        """Authenticate with Netz NO API.

        Returns:
            Self for method chaining

        Raises:
            SmartmeterLoginError: If authentication fails
            SmartmeterConnectionError: If connection fails
        """
        if self._is_authenticated and self._validate_session():
            return self

        logger.debug("Attempting login to %s", const.AUTH_URL)
        try:
            response = self.session.post(
                const.AUTH_URL, json={"user": self.username, "pwd": self.password}
            )
        except requests.exceptions.RequestException as e:
            logger.error("Connection error during login: %s", e)
            raise SmartmeterConnectionError(
                "Could not connect to Netz NO API"
            ) from e

        logger.debug("Login response status: %s", response.status_code)
        logger.debug("Login response headers: %s", dict(response.headers))
        try:
            logger.debug("Login response body: %s", response.text[:500])
        except Exception:
            pass

        if response.status_code != 200:
            raise SmartmeterLoginError(
                f"Login failed (HTTP {response.status_code}). Check username/password."
            )

        self._is_authenticated = True
        self._load_account_info()
        return self

    def _load_account_info(self):
        """Load account and metering point information after login."""
        # Get metering points (returns JSON array)
        response = self._call_api(const.ENDPOINT_METERING_POINTS)
        logger.debug("Metering points response: %s", response)

        if response and len(response) > 0:
            metering_point = response[0]
            self._metering_point_id = metering_point.get("meteringPointId")
            self._account_id = metering_point.get("accountId")
            self._has_smart_meter = metering_point.get("smartMeterType") is not None
            self._has_communicative = metering_point.get("communicative", False)
            self._has_active = not metering_point.get("locked", False)
            # Store full response for get_metering_points()
            self._metering_points_cache = response

    def _call_api(
        self,
        endpoint: str,
        method: str = "GET",
        query: Optional[Dict[str, Any]] = None,
        timeout: float = 60.0,
    ) -> Any:
        """Make API call to Netz NO endpoint.

        Args:
            endpoint: API endpoint (relative to BASE_URL)
            method: HTTP method
            query: Query parameters
            timeout: Request timeout

        Returns:
            JSON response from API

        Raises:
            SmartmeterConnectionError: If request fails
            SmartmeterQueryError: If response is invalid
        """
        if not self._is_authenticated:
            raise SmartmeterConnectionError(
                "Not authenticated. Call login() first."
            )

        url = parse.urljoin(const.BASE_URL, endpoint)

        if query:
            url += ("?" if "?" not in endpoint else "&") + parse.urlencode(query)

        try:
            response = self.session.request(method, url, timeout=timeout)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            if response.status_code == 401:
                self._is_authenticated = False
                raise SmartmeterLoginError("Session expired") from e
            raise SmartmeterQueryError(f"API error: {e}") from e
        except requests.exceptions.RequestException as e:
            raise SmartmeterConnectionError(f"Request failed: {e}") from e

    @property
    def account_id(self) -> Optional[str]:
        """Return the account ID."""
        return self._account_id

    @property
    def metering_point_id(self) -> Optional[str]:
        """Return the metering point ID."""
        return self._metering_point_id

    def get_metering_points(self) -> List[Dict[str, Any]]:
        """Get all metering points for the account.

        Returns:
            List of metering point dictionaries
        """
        return self._metering_points_cache

    def get_account_info(self) -> Dict[str, Any]:
        """Get account information.

        Returns:
            Dictionary with account info
        """
        return {
            "accountId": self._account_id,
            "meteringPointId": self._metering_point_id,
            "hasSmartMeter": self._has_smart_meter,
            "hasCommunicative": self._has_communicative,
            "hasActive": self._has_active,
        }

    def get_consumption_day(
        self, day: date, meter_id: Optional[str] = None
    ) -> Tuple[List[str], List[float]]:
        """Get daily consumption data.

        Args:
            day: Date to get consumption for
            meter_id: Metering point ID (uses default if None)

        Returns:
            Tuple of (peak_demand_times, metered_values)
        """
        meter_id = meter_id or self._metering_point_id
        if not meter_id:
            raise SmartmeterQueryError("No metering point ID available")

        response = self._call_api(
            const.ENDPOINT_CONSUMPTION_DAY,
            query={"meterId": meter_id, "day": day.strftime(const.API_DATE_FORMAT)},
        )
        logger.debug("ConsumptionDay raw response: %s", response)

        # API returns a list containing a dictionary - extract first element
        if isinstance(response, list) and len(response) > 0:
            response = response[0]
        elif isinstance(response, list):
            return ([], [])

        return (
            response.get("peakDemandTimes", []),
            response.get("meteredValues", []),
        )

    def get_consumption_month(
        self, year: int, month: int, meter_id: Optional[str] = None
    ) -> Tuple[List[str], List[float]]:
        """Get monthly consumption data.

        Args:
            year: Year
            month: Month (1-12)
            meter_id: Metering point ID (uses default if None)

        Returns:
            Tuple of (peak_demand_times, metered_values)
        """
        meter_id = meter_id or self._metering_point_id
        if not meter_id:
            raise SmartmeterQueryError("No metering point ID available")

        response = self._call_api(
            const.ENDPOINT_CONSUMPTION_MONTH,
            query={"meterId": meter_id, "year": year, "month": month},
        )

        # API returns a list containing a dictionary - extract first element
        if isinstance(response, list) and len(response) > 0:
            response = response[0]
        elif isinstance(response, list):
            return ([], [])

        return (
            response.get("peakDemandTimes", []),
            response.get("meteredValues", []),
        )

    def get_consumption_year(
        self, year: int, meter_id: Optional[str] = None
    ) -> Tuple[List[str], List[float]]:
        """Get yearly consumption data.

        Args:
            year: Year
            meter_id: Metering point ID (uses default if None)

        Returns:
            Tuple of (peak_demand_times, values)
        """
        meter_id = meter_id or self._metering_point_id
        if not meter_id:
            raise SmartmeterQueryError("No metering point ID available")

        response = self._call_api(
            const.ENDPOINT_CONSUMPTION_YEAR,
            query={"meterId": meter_id, "year": year},
        )

        # API returns a list containing a dictionary - extract first element
        if isinstance(response, list) and len(response) > 0:
            response = response[0]
        elif isinstance(response, list):
            return ([], [])

        return (
            response.get("peakDemandTimes", []),
            response.get("values", []),
        )

    def get_historical_consumption(
        self,
        start_date: date,
        end_date: Optional[date] = None,
        meter_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Get historical consumption data day by day.

        This fetches daily consumption for each day in the range.

        Args:
            start_date: Start date
            end_date: End date (defaults to today)
            meter_id: Metering point ID

        Returns:
            List of daily consumption records
        """
        if end_date is None:
            end_date = date.today()

        meter_id = meter_id or self._metering_point_id
        results = []

        current = start_date
        while current <= end_date:
            try:
                times, values = self.get_consumption_day(current, meter_id)
                results.append(
                    {
                        "date": current.isoformat(),
                        "peakDemandTimes": times,
                        "meteredValues": values,
                    }
                )
            except SmartmeterQueryError as e:
                logger.warning(f"Could not fetch data for {current}: {e}")
            current = current + timedelta(days=1)

        return results
