"""DataUpdateCoordinator for the Pure VMC VMC integration."""
from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import PureApi, PureApiError
from .const import DEFAULT_SCAN_INTERVAL, DOMAIN
from .modbus import PureModbus, PureModbusError, decode_registers

_LOGGER = logging.getLogger(__name__)


class PureCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Single coordinator shared by all Pure VMC entities.

    State is read over Modbus TCP when the unit offers it: one short exchange
    returns far more than the web pages do and leaves the unit's small web
    server alone. The web pages remain the fallback, and the only command path.
    """

    def __init__(
        self, hass: HomeAssistant, api: PureApi, modbus: PureModbus | None = None
    ) -> None:
        self.api = api
        self.modbus = modbus
        self._modbus_failing = False
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )

    async def async_write_register(
        self, register: int, value: int, mask: int = 0xFFFF
    ) -> None:
        """Write a register (verified by reading it back) and refresh the state."""
        assert self.modbus is not None
        await self.modbus.write_register(register, value, mask)
        # Not async_request_refresh(): its debouncer would leave the entities
        # showing the old state for up to 10 s when commands follow each other.
        await self.async_refresh()

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch all data from the device in one go."""
        if self.modbus is not None:
            try:
                data = decode_registers(await self.modbus.read_registers())
            except PureModbusError as err:
                if not self._modbus_failing:
                    _LOGGER.warning(
                        "Modbus read failed, falling back to the web pages: %s", err
                    )
                    self._modbus_failing = True
            else:
                if self._modbus_failing:
                    _LOGGER.info("Modbus is answering again")
                    self._modbus_failing = False
                return data

        try:
            return await self.api.get_all()
        except PureApiError as err:
            raise UpdateFailed(f"Error communicating with Pure VMC: {err}") from err
