"""API constants for Netz NO Smartmeter."""

# Netz NO API URLs
BASE_URL = "https://smartmeter.netz-noe.at/orchestration/"
AUTH_URL = "https://smartmeter.netz-noe.at/orchestration/Authentication/Login"

# API Endpoints (relative to BASE_URL)
ENDPOINT_USER_INFO = "User/GetBasicInfo"
ENDPOINT_METERING_POINTS = "User/GetMeteringPointsByBusinesspartnerId?context=2"
ENDPOINT_CONSUMPTION_DAY = "ConsumptionRecord/Day"
ENDPOINT_CONSUMPTION_MONTH = "ConsumptionRecord/Month"
ENDPOINT_CONSUMPTION_YEAR = "ConsumptionRecord/Year"

# Date formats
API_DATE_FORMAT = "%Y-%m-%d"
