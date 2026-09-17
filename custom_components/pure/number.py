"""Number entities for Pure VMC (set-point and boost timer, over Modbus)."""
from __future__ import annotations

from homeassistant.components.number import NumberDeviceClass, NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import PureCoordinator
from .entity_base import PureEntity
from .modbus import REG_BOOST_TIMER, REG_TEMP_SETPOINT


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: PureCoordinator = hass.data[DOMAIN][entry.entry_id]
    if coordinator.modbus is None:
        return
    async_add_entities(
        [
            PureSetpointNumber(coordinator, entry.entry_id),
            PureBoostNumber(coordinator, entry.entry_id),
        ]
    )


class PureSetpointNumber(PureEntity, NumberEntity):
    """The target temperature. The unit stores it in steps of 0.2 degrees."""

    _attr_translation_key = "temp_setpoint"
    _attr_device_class = NumberDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_native_min_value = 5.0
    _attr_native_max_value = 30.0
    _attr_native_step = 0.2
    _attr_mode = NumberMode.BOX

    def __init__(self, coordinator: PureCoordinator, entry_id: str) -> None:
        super().__init__(coordinator, entry_id)
        self._attr_unique_id = f"{entry_id}_temp_setpoint_number"

    @property
    def native_value(self) -> float | None:
        return self.coordinator.data.get("temp_setpoint")

    async def async_set_native_value(self, value: float) -> None:
        # Tenths of a degree, rounded to the even values the unit accepts
        await self._async_write_register(REG_TEMP_SETPOINT, round(value * 5) * 2)


class PureBoostNumber(PureEntity, NumberEntity):
    """Minutes of boost left. Setting it starts a boost; 0 cancels it."""

    _attr_translation_key = "boost_timer"
    _attr_native_unit_of_measurement = UnitOfTime.MINUTES
    _attr_native_min_value = 0
    _attr_native_max_value = 240
    _attr_native_step = 1
    _attr_mode = NumberMode.BOX
    _attr_icon = "mdi:fan-clock"

    def __init__(self, coordinator: PureCoordinator, entry_id: str) -> None:
        super().__init__(coordinator, entry_id)
        self._attr_unique_id = f"{entry_id}_boost_timer"

    @property
    def native_value(self) -> int | None:
        seconds = self.coordinator.data.get("boost_remaining")
        if seconds is None:
            return None
        return -(-seconds // 60)  # round up, so a running boost never reads 0

    async def async_set_native_value(self, value: float) -> None:
        await self._async_write_register(REG_BOOST_TIMER, int(value) * 60, store=False)
