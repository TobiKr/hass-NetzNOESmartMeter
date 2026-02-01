"""Fixtures for Netz NO Smartmeter tests."""
import pytest

from unittest.mock import patch, MagicMock

pytest_plugins = "pytest_homeassistant_custom_component"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Enable custom integrations for all tests."""
    yield


@pytest.fixture
def mock_smartmeter():
    """Create a mock Smartmeter client."""
    with patch(
        "custom_components.netznoe.config_flow.Smartmeter"
    ) as mock_class:
        mock_instance = MagicMock()
        mock_instance.login.return_value = None
        mock_instance.get_account_info.return_value = {
            "accountId": "12345",
            "hasSmartMeter": True,
            "hasElectricity": True,
            "hasGas": False,
            "hasCommunicative": True,
            "hasOptIn": True,
            "hasActive": True,
        }
        mock_instance.get_metering_points.return_value = [
            {"meteringPointId": "AT0010000000000000001000000000001"}
        ]
        mock_class.return_value = mock_instance
        yield mock_instance


@pytest.fixture
def mock_smartmeter_no_smartmeter():
    """Create a mock Smartmeter client without smart meter."""
    with patch(
        "custom_components.netznoe.config_flow.Smartmeter"
    ) as mock_class:
        mock_instance = MagicMock()
        mock_instance.login.return_value = None
        mock_instance.get_account_info.return_value = {
            "accountId": "12345",
            "hasSmartMeter": False,
            "hasElectricity": True,
            "hasGas": False,
            "hasCommunicative": False,
            "hasOptIn": False,
            "hasActive": True,
        }
        mock_class.return_value = mock_instance
        yield mock_instance
