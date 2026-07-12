"""Sensor entities for Pure VMC."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, SPEED_TIMER_MODE
from .coordinator import PureCoordinator
from .entity_base import PureEntity

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class PureSensorDescription(SensorEntityDescription):
    """Extends SensorEntityDescription with a coordinator data key."""
    data_key: str


TEMPERATURE_SENSORS: tuple[PureSensorDescription, ...] = (
    PureSensorDescription(
        key="temp_external",
        data_key="temp_external",
        translation_key="temp_external",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        suggested_display_precision=1,
    ),
    PureSensorDescription(
        key="temp_return",
        data_key="temp_return",
        translation_key="temp_return",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        suggested_display_precision=1,
    ),
    PureSensorDescription(
        key="temp_exhaust",
        data_key="temp_exhaust",
        translation_key="temp_exhaust",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        suggested_display_precision=1,
    ),
    PureSensorDescription(
        key="temp_inlet",
        data_key="temp_inlet",
        translation_key="temp_inlet",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        suggested_display_precision=1,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: PureCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities: list[PureEntity] = []

    for desc in TEMPERATURE_SENSORS:
        entities.append(PureTemperatureSensor(coordinator, entry.entry_id, desc))

    entities.append(PureSpeedSensor(coordinator, entry.entry_id))
    entities.append(PureEfficiencySensor(coordinator, entry.entry_id))

    async_add_entities(entities)


# ---------------------------------------------------------------------------
# Temperature sensors
# ---------------------------------------------------------------------------

class PureTemperatureSensor(PureEntity, SensorEntity):
    """One of the four temperature measurement points."""

    entity_description: PureSensorDescription

    def __init__(
        self,
        coordinator: PureCoordinator,
        entry_id: str,
        description: PureSensorDescription,
    ) -> None:
        super().__init__(coordinator, entry_id)
        self.entity_description = description
        self._attr_unique_id = f"{entry_id}_{description.key}"

    @property
    def native_value(self) -> float | None:
        return self.coordinator.data.get(self.entity_description.data_key)


# ---------------------------------------------------------------------------
# Speed sensor
# ---------------------------------------------------------------------------

class PureSpeedSensor(PureEntity, SensorEntity):
    """
    Ventilation speed as a percentage.

    Values:
      0    → off
      10–100 → normal operation
      101  → Orologio (internal timer schedule active)
    """

    _attr_translation_key = "speed"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "%"
    _attr_icon = "mdi:speedometer"

    def __init__(self, coordinator: PureCoordinator, entry_id: str) -> None:
        super().__init__(coordinator, entry_id)
        self._attr_unique_id = f"{entry_id}_speed"

    @property
    def native_value(self) -> int | None:
        return self.coordinator.data.get("speed")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        speed = self.coordinator.data.get("speed")
        return {
            "timer_mode": self.coordinator.data.get("timer_mode", False),
            # Convenient boolean for automations: is the fan actually running?
            "is_running": speed is not None and speed > 0,
        }


# ---------------------------------------------------------------------------
# Heat recovery efficiency sensor
# ---------------------------------------------------------------------------

class PureEfficiencySensor(PureEntity, SensorEntity):
    """
    Computed heat recovery efficiency in %.

    Formula (heating mode): η = (T_inlet - T_external) / (T_return - T_external) × 100
    Formula (cooling mode): η = (T_external - T_inlet) / (T_external - T_return) × 100

    Clamped to [0, 100].
    Only computed when speed > 0 and not in timer mode (to avoid division issues
    when the fan is off or running an unknown schedule).
    """

    _attr_translation_key = "heat_recovery_efficiency"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "%"
    _attr_icon = "mdi:heat-pump"
    _attr_suggested_display_precision = 1

    def __init__(self, coordinator: PureCoordinator, entry_id: str) -> None:
        super().__init__(coordinator, entry_id)
        self._attr_unique_id = f"{entry_id}_heat_recovery_efficiency"

    @property
    def native_value(self) -> float | None:
        data = self.coordinator.data
        speed = data.get("speed", 0)

        # Don't compute when off or in timer mode (speed unknown)
        if speed == 0 or speed == SPEED_TIMER_MODE:
            return None

        t_ext = data.get("temp_external")
        t_ret = data.get("temp_return")
        t_in = data.get("temp_inlet")

        if any(v is None for v in (t_ext, t_ret, t_in)):
            return None

        delta = t_ret - t_ext

        if delta == 0:
            return 0.0

        if delta > 0:
            # Heating mode: outdoor is colder than indoor
            eff = (t_in - t_ext) / delta * 100
        else:
            # Cooling mode: outdoor is hotter than indoor
            eff = (t_ext - t_in) / (t_ext - t_ret) * 100

        return round(max(0.0, min(100.0, eff)), 1)
