"""Test the Netz NO Smartmeter config flow."""
from unittest.mock import patch, MagicMock

import pytest
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.netznoe.const import DOMAIN
from custom_components.netznoe.api.errors import (
    SmartmeterLoginError,
    SmartmeterConnectionError,
)


async def test_form_user_step(hass: HomeAssistant, mock_smartmeter):
    """Test the user step shows form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}


async def test_form_user_success(hass: HomeAssistant, mock_smartmeter):
    """Test successful user authentication."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "username": "test@example.com",
            "password": "testpassword",
        },
    )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "Netz NO Smartmeter"
    assert result["data"]["username"] == "test@example.com"
    assert result["data"]["password"] == "testpassword"
    assert "metering_points" in result["data"]
    assert "account_info" in result["data"]


async def test_form_invalid_auth(hass: HomeAssistant):
    """Test handling of invalid authentication."""
    with patch(
        "custom_components.netznoe.config_flow.Smartmeter"
    ) as mock_class:
        mock_instance = MagicMock()
        mock_instance.login.side_effect = SmartmeterLoginError("Invalid credentials")
        mock_class.return_value = mock_instance

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "username": "bad@example.com",
                "password": "wrongpassword",
            },
        )

        assert result["type"] == FlowResultType.FORM
        assert result["errors"] == {"base": "auth"}


async def test_form_connection_error(hass: HomeAssistant):
    """Test handling of connection errors."""
    with patch(
        "custom_components.netznoe.config_flow.Smartmeter"
    ) as mock_class:
        mock_instance = MagicMock()
        mock_instance.login.side_effect = SmartmeterConnectionError("Connection failed")
        mock_class.return_value = mock_instance

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "username": "test@example.com",
                "password": "testpassword",
            },
        )

        assert result["type"] == FlowResultType.FORM
        assert result["errors"] == {"base": "connection_error"}


async def test_form_no_smartmeter(hass: HomeAssistant, mock_smartmeter_no_smartmeter):
    """Test handling when account has no smart meter."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "username": "test@example.com",
            "password": "testpassword",
        },
    )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "no_smartmeter"}


async def test_form_not_active(hass: HomeAssistant):
    """Test handling when account is not active."""
    with patch(
        "custom_components.netznoe.config_flow.Smartmeter"
    ) as mock_class:
        mock_instance = MagicMock()
        mock_instance.login.return_value = None
        mock_instance.get_account_info.return_value = {
            "accountId": "12345",
            "hasSmartMeter": True,
            "hasActive": False,
        }
        mock_class.return_value = mock_instance

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "username": "test@example.com",
                "password": "testpassword",
            },
        )

        assert result["type"] == FlowResultType.FORM
        assert result["errors"] == {"base": "not_active"}
