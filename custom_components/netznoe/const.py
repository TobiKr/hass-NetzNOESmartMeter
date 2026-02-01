"""Component constants for Netz NO Smartmeter."""
DOMAIN = "netznoe"

CONF_METERING_POINTS = "metering_points"

# Attribute mappings for Netz NO API responses

# From /User/GetAccountIdByBussinespartnerId response
ATTRS_ACCOUNT_INFO = [
    ("accountId", "accountId"),
    ("hasSmartMeter", "hasSmartMeter"),
    ("hasElectricity", "hasElectricity"),
    ("hasGas", "hasGas"),
    ("hasCommunicative", "hasCommunicative"),
    ("hasOptIn", "hasOptIn"),
    ("hasActive", "hasActive"),
]

# From /User/GetMeteringPointByAccountId response
ATTRS_METERING_POINT = [
    ("meteringPointId", "meteringPointId"),
]

# From /ConsumptionRecord/Day response
ATTRS_CONSUMPTION_DAY = [
    ("peakDemandTimes", "peakDemandTimes"),
    ("meteredValues", "meteredValues"),
]

# From /ConsumptionRecord/Month response
ATTRS_CONSUMPTION_MONTH = [
    ("peakDemandTimes", "peakDemandTimes"),
    ("meteredValues", "meteredValues"),
]

# From /ConsumptionRecord/Year response
ATTRS_CONSUMPTION_YEAR = [
    ("peakDemandTimes", "peakDemandTimes"),
    ("values", "values"),
]
