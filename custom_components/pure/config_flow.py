"""Config flow for Pure VMC."""
from __future__ import annotations

import logging
import re
from typing import Any

import aiohttp
import voluptuous as vol
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .api import PureApi
from .const import (
    CONF_FILTER_INTERVAL,
    CONF_HOST,
    CONF_INSTALLER_CODE,
    CONF_MODBUS,
    DEFAULT_FILTER_INTERVAL,
    DEFAULT_MODBUS,
    DOMAIN,
)
from .menu import FILTER_HOURS_STEP

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST, description={"suggested_value": "192.168.1.x"}): str,
    }
)


class PureConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the initial setup UI."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return PureOptionsFlow()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            host = user_input[CONF_HOST].strip()
            session = async_get_clientsession(self.hass)
            api = PureApi(host, session)

            if await api.test_connection():
                # Avoid duplicate entries for the same host
                await self.async_set_unique_id(host)
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=f"Pure VMC ({host})",
                    data={CONF_HOST: host},
                )
            else:
                errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )


class PureOptionsFlow(OptionsFlow):
    """Modbus on/off, and the installer code for the filter-alarm threshold."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        options = self.config_entry.options
        if user_input is not None:
            code = (user_input.get(CONF_INSTALLER_CODE) or "").strip()
            if code and not re.fullmatch(r"\d{4}", code):
                errors[CONF_INSTALLER_CODE] = "invalid_installer_code"
            else:
                data = {**user_input}
                data.pop(CONF_INSTALLER_CODE, None)
                if code:
                    data[CONF_INSTALLER_CODE] = code
                data[CONF_FILTER_INTERVAL] = int(user_input[CONF_FILTER_INTERVAL])
                return self.async_create_entry(data=data)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_MODBUS,
                        default=options.get(CONF_MODBUS, DEFAULT_MODBUS),
                    ): bool,
                    vol.Optional(
                        CONF_INSTALLER_CODE,
                        description={
                            "suggested_value": options.get(CONF_INSTALLER_CODE, "")
                        },
                    ): TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD)),
                    vol.Required(
                        CONF_FILTER_INTERVAL,
                        default=options.get(CONF_FILTER_INTERVAL, DEFAULT_FILTER_INTERVAL),
                    ): NumberSelector(
                        NumberSelectorConfig(
                            min=FILTER_HOURS_STEP,
                            max=20000,
                            step=FILTER_HOURS_STEP,
                            unit_of_measurement="h",
                            mode=NumberSelectorMode.BOX,
                        )
                    ),
                }
            ),
            errors=errors,
        )
