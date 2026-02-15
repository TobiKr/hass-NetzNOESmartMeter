"""Component constants for Netz NO Smartmeter."""
DOMAIN = "netznoe"

CONF_METERING_POINTS = "metering_points"


def is_meter_active(metering_point_data: dict) -> bool:
    """Check if a specific metering point is an active smart meter."""
    has_smart = metering_point_data.get("smartMeterType") is not None
    is_active = not metering_point_data.get("locked", False)
    return has_smart and is_active

