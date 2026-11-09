"""Diagnostics for Pure VMC: the decoded state and the raw Modbus registers."""
from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import CONF_HOST, CONF_INSTALLER_CODE, DOMAIN
from .coordinator import PureCoordinator
from .modbus import READ_BLOCKS, PureModbusError

# The installer code is the manufacturer's, the same on every unit: a download
# shared in an issue must not carry it.
TO_REDACT = {CONF_HOST, CONF_INSTALLER_CODE}

# The polled blocks plus the PID/timer parameters, which are not decoded but
# help telling unit variants apart.
DIAGNOSTIC_BLOCKS = (*READ_BLOCKS, (32, 7))


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    coordinator: PureCoordinator = hass.data[DOMAIN][entry.entry_id]

    registers: dict[str, int] | str | None = None
    if coordinator.modbus is not None:
        try:
            raw = await coordinator.modbus.read_registers(DIAGNOSTIC_BLOCKS)
            registers = {str(number): raw[number] for number in sorted(raw)}
        except PureModbusError as err:
            registers = f"read failed: {err}"

    return {
        "entry": {
            "data": async_redact_data(dict(entry.data), TO_REDACT),
            "options": async_redact_data(dict(entry.options), TO_REDACT),
        },
        "modbus": coordinator.modbus is not None,
        "data": coordinator.data,
        "registers": registers,
    }
