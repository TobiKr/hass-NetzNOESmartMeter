"""Config flow for Netz NO Smartmeter integration."""
import logging
from typing import Any, Optional

import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME

from .api import Smartmeter
from .api.errors import SmartmeterConnectionError, SmartmeterLoginError
from .const import CONF_METERING_POINTS, DOMAIN

_LOGGER = logging.getLogger(__name__)

AUTH_SCHEMA = vol.Schema(
    {vol.Required(CONF_USERNAME): cv.string, vol.Required(CONF_PASSWORD): cv.string}
)


class NetzNoeSmartmeterConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Netz NO Smartmeter config flow."""

    VERSION = 1
    data: Optional[dict[str, Any]] = None

    async def validate_auth(self, username: str, password: str) -> dict:
        """Validate credentials and return account info.

        Raises ValueError if credentials are invalid.
        """
        smartmeter = Smartmeter(username, password)
        await self.hass.async_add_executor_job(smartmeter.login)

        account_info = smartmeter.get_account_info()
        metering_points = await self.hass.async_add_executor_job(
            smartmeter.get_metering_points
        )

        return {"account_info": account_info, "metering_points": metering_points}

    async def async_step_user(self, user_input: Optional[dict[str, Any]] = None):
        """Handle user step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                result = await self.validate_auth(
                    user_input[CONF_USERNAME], user_input[CONF_PASSWORD]
                )
            except SmartmeterLoginError as e:
                _LOGGER.error("Invalid Netz NO credentials: %s", e)
                errors["base"] = "auth"
            except SmartmeterConnectionError as e:
                _LOGGER.error("Could not connect to Netz NO API: %s", e)
                errors["base"] = "connection_error"
            except Exception as e:
                _LOGGER.exception("Unexpected error during Netz NO auth: %s", e)
                errors["base"] = "auth"
            else:
                # Check if we have active smart meter
                account_info = result["account_info"]
                if not account_info.get("hasSmartMeter"):
                    errors["base"] = "no_smartmeter"
                elif not account_info.get("hasActive"):
                    errors["base"] = "not_active"
                else:
                    # Success - create entry
                    self.data = user_input
                    self.data[CONF_METERING_POINTS] = result["metering_points"]
                    self.data["account_info"] = result["account_info"]

                    return self.async_create_entry(
                        title="Netz NO Smartmeter", data=self.data
                    )

        return self.async_show_form(
            step_id="user", data_schema=AUTH_SCHEMA, errors=errors
        )
