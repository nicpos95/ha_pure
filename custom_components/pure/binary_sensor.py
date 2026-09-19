"""Binary sensor entities for Pure VMC."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import PureCoordinator
from .entity_base import PureEntity


@dataclass(frozen=True, kw_only=True)
class PureBinarySensorDescription(BinarySensorEntityDescription):
    """Binary sensor description with a value getter over coordinator data."""

    value_fn: Callable[[dict[str, Any]], bool | None]


BINARY_SENSORS: tuple[PureBinarySensorDescription, ...] = (
    PureBinarySensorDescription(
        key="filter",
        translation_key="filter",
        device_class=BinarySensorDeviceClass.PROBLEM,
        value_fn=lambda data: data.get("filter_dirty"),
    ),
    PureBinarySensorDescription(
        key="alarm",
        translation_key="alarm",
        device_class=BinarySensorDeviceClass.PROBLEM,
        value_fn=lambda data: data.get("alarm_active"),
    ),
    PureBinarySensorDescription(
        key="bypass",
        translation_key="bypass",
        icon="mdi:valve",
        value_fn=lambda data: data.get("bypass"),
    ),
)

# The individual entries of the unit's Alarms screen. Only Modbus reports them
# one by one, so these are created only when the unit is read over Modbus.
FAULTS: tuple[str, ...] = (
    "fault_communication",
    "fault_configuration",
    "fault_temp_external",
    "fault_temp_return",
    "fault_temp_exhaust",
    "fault_temp_inlet",
    "fault_fans",
    "fault_anti_frost",
)

MODBUS_BINARY_SENSORS: tuple[PureBinarySensorDescription, ...] = (
    PureBinarySensorDescription(
        key="anti_frost",
        translation_key="anti_frost",
        icon="mdi:snowflake-alert",
        value_fn=lambda data: data.get("anti_frost"),
    ),
    *(
        PureBinarySensorDescription(
            key=fault,
            translation_key=fault,
            device_class=BinarySensorDeviceClass.PROBLEM,
            entity_category=EntityCategory.DIAGNOSTIC,
            value_fn=lambda data, fault=fault: data.get(fault),
        )
        for fault in FAULTS
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: PureCoordinator = hass.data[DOMAIN][entry.entry_id]
    descriptions = BINARY_SENSORS
    if coordinator.modbus is not None:
        descriptions += MODBUS_BINARY_SENSORS
    async_add_entities(
        PureBinarySensor(coordinator, entry.entry_id, description)
        for description in descriptions
    )


class PureBinarySensor(PureEntity, BinarySensorEntity):
    """A single Pure VMC binary status point."""

    entity_description: PureBinarySensorDescription

    def __init__(
        self,
        coordinator: PureCoordinator,
        entry_id: str,
        description: PureBinarySensorDescription,
    ) -> None:
        super().__init__(coordinator, entry_id)
        self.entity_description = description
        self._attr_unique_id = f"{entry_id}_{description.key}"

    @property
    def is_on(self) -> bool | None:
        """Return the state, or None (unknown) when the value could not be read."""
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        data = self.coordinator.data
        # Surface the raw alarm banner on the filter sensor so a different alarm
        # (which leaves the filter sensor off) is still visible to the user.
        # Only the web pages carry the banner; Modbus names the alarms instead.
        if self.entity_description.key == "filter" and "alarm_banner" in data:
            return {"alarm_banner": data["alarm_banner"]}
        if self.entity_description.key == "alarm" and "active_alarms" in data:
            return {"active_alarms": data["active_alarms"]}
        return None
