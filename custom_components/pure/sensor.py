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
from homeassistant.const import (
    PERCENTAGE,
    REVOLUTIONS_PER_MINUTE,
    EntityCategory,
    UnitOfTemperature,
    UnitOfTime,
)
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


# The target temperature that drives the bypass (free-cooling) logic. It is a
# set-point rather than a measurement point, so it is kept out of the tuple above.
SETPOINT_SENSOR = PureSensorDescription(
    key="temp_setpoint",
    data_key="temp_setpoint",
    translation_key="temp_setpoint",
    device_class=SensorDeviceClass.TEMPERATURE,
    state_class=SensorStateClass.MEASUREMENT,
    native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    suggested_display_precision=1,
)


# Values only Modbus reports; created only when the unit is read over Modbus.
# The two fan speeds are described separately because their unit depends on
# how the unit is built (see ``_fan_speed_sensors``).
MODBUS_SENSORS: tuple[PureSensorDescription, ...] = (
    PureSensorDescription(
        key="fan_hours",
        data_key="fan_hours",
        translation_key="fan_hours",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfTime.HOURS,
        icon="mdi:timer-outline",
    ),
    PureSensorDescription(
        key="boost_remaining",
        data_key="boost_remaining",
        translation_key="boost_remaining",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        icon="mdi:fan-clock",
    ),
    PureSensorDescription(
        key="operating_mode",
        data_key="operating_mode",
        translation_key="operating_mode",
        device_class=SensorDeviceClass.ENUM,
        options=["off", "manual", "schedule", "auto", "boost"],
        icon="mdi:hvac",
    ),
    PureSensorDescription(
        key="filter_max_hours",
        data_key="filter_max_hours",
        translation_key="filter_max_hours",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.HOURS,
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:air-filter",
    ),
)


# Shown instead of the bypass mode select on units that do not let it be chosen
BYPASS_MODE_SENSOR = PureSensorDescription(
    key="bypass_mode",
    data_key="bypass_mode",
    translation_key="bypass_mode",
    device_class=SensorDeviceClass.ENUM,
    options=["auto", "off", "on"],
    entity_category=EntityCategory.DIAGNOSTIC,
    icon="mdi:valve",
)


def _fan_speed_sensors(is_rpm: bool) -> tuple[PureSensorDescription, ...]:
    """The measured fan speeds: RPM when the fans have a tacho signal, else %."""
    return tuple(
        PureSensorDescription(
            key=key,
            data_key=key,
            translation_key=key,
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=REVOLUTIONS_PER_MINUTE if is_rpm else PERCENTAGE,
            icon="mdi:fan",
        )
        for key in ("fan_supply_speed", "fan_exhaust_speed")
    )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: PureCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities: list[PureEntity] = []

    for desc in TEMPERATURE_SENSORS:
        entities.append(PureValueSensor(coordinator, entry.entry_id, desc))

    entities.append(PureValueSensor(coordinator, entry.entry_id, SETPOINT_SENSOR))
    entities.append(PureSpeedSensor(coordinator, entry.entry_id))
    entities.append(PureEfficiencySensor(coordinator, entry.entry_id))

    if coordinator.modbus is not None:
        is_rpm = bool(coordinator.data.get("fan_speed_is_rpm"))
        for desc in (*_fan_speed_sensors(is_rpm), *MODBUS_SENSORS):
            entities.append(PureValueSensor(coordinator, entry.entry_id, desc))
        if not coordinator.data.get("bypass_mode_selectable"):
            entities.append(
                PureValueSensor(coordinator, entry.entry_id, BYPASS_MODE_SENSOR)
            )

    async_add_entities(entities)


# ---------------------------------------------------------------------------
# Plain value sensors (temperatures and the Modbus-only readings)
# ---------------------------------------------------------------------------

class PureValueSensor(PureEntity, SensorEntity):
    """A sensor that reports one coordinator value as-is."""

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
    def native_value(self) -> float | int | str | None:
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
    Only computed while the fans run. Over Modbus that is the measured supply
    fan speed; from the web pages only the set-point is known, so timer mode
    (running an unknown schedule) is skipped as well.
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

        if "fan_supply_speed" in data:
            if not data["fan_supply_speed"]:
                return None
        # Don't compute when off or in timer mode (speed unknown)
        elif speed == 0 or speed == SPEED_TIMER_MODE:
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
