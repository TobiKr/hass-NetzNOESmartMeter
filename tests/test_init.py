"""Test component setup."""
from unittest.mock import patch, MagicMock

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntryState

from custom_components.netznoe.const import DOMAIN


async def test_setup_entry(hass: HomeAssistant):
    """Test setting up the integration."""
    entry = MagicMock()
    entry.entry_id = "test_entry_id"
    entry.data = {
        "username": "test@example.com",
        "password": "testpassword",
        "metering_points": [{"meteringPointId": "AT001"}],
        "account_info": {"accountId": "12345"},
    }

    with patch(
        "custom_components.netznoe.sensor.async_setup_entry",
        return_value=True,
    ):
        from custom_components.netznoe import async_setup_entry

        result = await async_setup_entry(hass, entry)

        assert result is True
        assert DOMAIN in hass.data
        assert entry.entry_id in hass.data[DOMAIN]
        assert hass.data[DOMAIN][entry.entry_id] == entry.data


async def test_unload_entry(hass: HomeAssistant):
    """Test unloading the integration."""
    entry = MagicMock()
    entry.entry_id = "test_entry_id"
    entry.data = {
        "username": "test@example.com",
        "password": "testpassword",
    }

    # Setup first
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = entry.data

    with patch.object(
        hass.config_entries,
        "async_unload_platforms",
        return_value=True,
    ):
        from custom_components.netznoe import async_unload_entry

        result = await async_unload_entry(hass, entry)

        assert result is True
        assert entry.entry_id not in hass.data[DOMAIN]


def test_domain_constant():
    """Test that the DOMAIN constant is set correctly."""
    assert DOMAIN == "netznoe"
