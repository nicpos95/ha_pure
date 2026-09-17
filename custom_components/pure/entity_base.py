"""Shared base entity for Pure VMC."""
from __future__ import annotations

from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import PureCoordinator
from .modbus import PureModbusError


class PureEntity(CoordinatorEntity[PureCoordinator]):
    """Base class that wires up coordinator and device info."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: PureCoordinator, entry_id: str) -> None:
        super().__init__(coordinator)
        self._entry_id = entry_id

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry_id)},
            name="Pure VMC",
            manufacturer="Pure",
            model="Pure VMC",
            # Only known when the unit is read over Modbus
            sw_version=self.coordinator.data.get("sw_version"),
        )

    async def _async_write_register(
        self, register: int, value: int, mask: int = 0xFFFF
    ) -> None:
        """Write over Modbus, surfacing a refusal as an error the user can read."""
        try:
            await self.coordinator.async_write_register(register, value, mask)
        except PureModbusError as err:
            raise HomeAssistantError(str(err)) from err
