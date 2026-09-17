"""DataUpdateCoordinator for the Pure VMC VMC integration."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from time import monotonic
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CALLBACK_TYPE, HomeAssistant
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import PureApi, PureApiError
from .const import DEFAULT_SCAN_INTERVAL, DOMAIN
from .modbus import (
    PureModbus,
    PureModbusError,
    PureModbusWriteIgnored,
    decode_registers,
)

_LOGGER = logging.getLogger(__name__)

# The unit drops Modbus writes for 60 s after a change made from its web page
# or touch panel. A dropped write is kept and tried again until it goes through.
WRITE_RETRY_INTERVAL = 15  # seconds
WRITE_RETRY_WINDOW = 180  # seconds before a write that keeps being dropped is given up


class PureCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Single coordinator shared by all Pure VMC entities.

    State is read over Modbus TCP when the unit offers it: one short exchange
    returns far more than the web pages do and leaves the unit's small web
    server alone. The web pages remain the fallback, and the only command path.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        api: PureApi,
        modbus: PureModbus | None = None,
    ) -> None:
        self.api = api
        self.modbus = modbus
        self._modbus_failing = False
        # Dropped writes waiting for the unit: (register, mask) -> (value, deadline)
        self._pending_writes: dict[tuple[int, int], tuple[int, float]] = {}
        self._cancel_retry: CALLBACK_TYPE | None = None
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )

    async def async_write_register(
        self, register: int, value: int, mask: int = 0xFFFF, *, retry: bool = True
    ) -> None:
        """Write a register (verified by reading it back) and refresh the state.

        When the unit drops the write, it is queued and retried until the unit
        accepts writes again; with ``retry=False`` the refusal is raised instead,
        for callers that have another way to deliver the command.
        """
        assert self.modbus is not None
        key = (register, mask)
        # A newer command for the same setting replaces one still waiting
        self._pending_writes.pop(key, None)
        try:
            await self.modbus.write_register(register, value, mask)
        except PureModbusWriteIgnored:
            if not retry:
                raise
            _LOGGER.info(
                "The unit is not accepting Modbus writes right now; the write to "
                "register %s will be retried for up to %s s",
                register,
                WRITE_RETRY_WINDOW,
            )
            self._pending_writes[key] = (value, monotonic() + WRITE_RETRY_WINDOW)
            self._schedule_retry()
            return
        # Not async_request_refresh(): its debouncer would leave the entities
        # showing the old state for up to 10 s when commands follow each other.
        await self.async_refresh()

    def _schedule_retry(self) -> None:
        if self._cancel_retry is None:
            self._cancel_retry = async_call_later(
                self.hass, WRITE_RETRY_INTERVAL, self._async_retry_writes
            )

    async def _async_retry_writes(self, _now: datetime) -> None:
        self._cancel_retry = None
        assert self.modbus is not None
        written = False
        for key, pending in list(self._pending_writes.items()):
            (register, mask), (value, deadline) = key, pending
            try:
                await self.modbus.write_register(register, value, mask)
            except PureModbusError as err:
                if monotonic() >= deadline and self._pending_writes.get(key) == pending:
                    del self._pending_writes[key]
                    _LOGGER.warning(
                        "Giving up on the write to register %s: %s", register, err
                    )
                continue
            written = True
            # Unless a newer command took its place while this one was written
            if self._pending_writes.get(key) == pending:
                del self._pending_writes[key]
        if written:
            await self.async_refresh()
        if self._pending_writes:
            self._schedule_retry()

    async def async_shutdown(self) -> None:
        if self._cancel_retry is not None:
            self._cancel_retry()
            self._cancel_retry = None
        self._pending_writes.clear()
        await super().async_shutdown()

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
