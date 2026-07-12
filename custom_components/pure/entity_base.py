"""Shared base entity for Pure VMC."""
from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import PureCoordinator


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
        )
