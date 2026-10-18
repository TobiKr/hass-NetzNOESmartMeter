"""Component constants for Netz NO Smartmeter."""
DOMAIN = "netznoe"

CONF_METERING_POINTS = "metering_points"

# Options
CONF_IMPORT_ESTIMATED_VALUES = "import_estimated_values"
CONF_REIMPORT_DAYS = "reimport_days"

DEFAULT_IMPORT_ESTIMATED_VALUES = False
DEFAULT_REIMPORT_DAYS = 7
MAX_REIMPORT_DAYS = 60


def is_meter_active(metering_point_data: dict) -> bool:
    """Check if a specific metering point is an active smart meter."""
    has_smart = metering_point_data.get("smartMeterType") is not None
    is_active = not metering_point_data.get("locked", False)
    return has_smart and is_active

