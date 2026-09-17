"""Fan entity for Pure VMC."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, SPEED_MAX, SPEED_MIN, SPEED_OFF
from .coordinator import PureCoordinator
from .entity_base import PureEntity
from .modbus import (
    REG_BOOST_TIMER,
    REG_SPEED_SETPOINT,
    SPEED_SETPOINT_TIMER,
    PureModbusError,
)

_LOGGER = logging.getLogger(__name__)

PRESET_NORMAL = "normal"
PRESET_BOOST = "boost"
PRESET_SCHEDULE = "schedule"  # the unit's weekly programme; needs Modbus
PRESET_MODES = [PRESET_NORMAL, PRESET_BOOST]

# Length of a boost started from the preset (the boost timer number entity
# starts one of any length)
DEFAULT_BOOST_SECONDS = 15 * 60


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: PureCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([PureFan(coordinator, entry.entry_id)])


class PureFan(PureEntity, FanEntity):
    """
    Controls the Pure fan speed.

    Supports:
      - turn_on / turn_off
      - set_percentage (10–100 in steps of 1)
      - boost (extra service, triggers the internal timer mode)

    Timer mode (Orologio, reported as 101) is read-only from this entity;
    it can only be exited by turning the unit off/on.

    When the unit is read over Modbus, commands go the same way: the speed is
    written directly instead of being stepped to with the web page's +/-
    buttons, and the weekly programme becomes a selectable "schedule" preset.
    The unit drops Modbus writes for 60 s after a change made from its web page
    or touch panel; speed commands then fall back to the web interface.
    """

    _attr_translation_key = "fan"
    _attr_icon = "mdi:hvac"
    _attr_preset_modes = PRESET_MODES
    _attr_supported_features = (
        FanEntityFeature.SET_SPEED
        | FanEntityFeature.TURN_ON
        | FanEntityFeature.TURN_OFF
        | FanEntityFeature.PRESET_MODE
    )

    def __init__(self, coordinator: PureCoordinator, entry_id: str) -> None:
        super().__init__(coordinator, entry_id)
        self._attr_unique_id = f"{entry_id}_fan"
        if coordinator.modbus is not None:
            self._attr_preset_modes = [*PRESET_MODES, PRESET_SCHEDULE]
        # Speed to come back to when turned on without a percentage
        self._last_speed = SPEED_MIN
        self._remember_speed()

    def _remember_speed(self) -> None:
        speed = self.coordinator.data.get("speed") or 0
        if SPEED_MIN <= speed <= SPEED_MAX:
            self._last_speed = speed

    def _handle_coordinator_update(self) -> None:
        self._remember_speed()
        super()._handle_coordinator_update()

    # ------------------------------------------------------------------
    # State properties
    # ------------------------------------------------------------------

    @property
    def is_on(self) -> bool:
        speed = self.coordinator.data.get("speed", 0)
        return speed > 0

    @property
    def percentage(self) -> int | None:
        speed = self.coordinator.data.get("speed")
        if speed is None:
            return None
        if speed > SPEED_MAX:
            # Timer mode (101) or auto mode (102): we report 100 so automations
            # using percentage don't get confused by the out-of-range value.
            # The timer_mode attribute on the speed sensor is the precise indicator.
            return 100
        return speed


    @property
    def preset_mode(self) -> str | None:
        """Return current preset mode."""
        mode = self.coordinator.data.get("operating_mode")
        if mode is not None:  # read over Modbus, which tells the modes apart
            if mode == "off":
                return None
            return {"boost": PRESET_BOOST, "schedule": PRESET_SCHEDULE}.get(
                mode, PRESET_NORMAL
            )
        if self.coordinator.data.get("timer_mode"):
            return PRESET_BOOST
        if self.coordinator.data.get("speed", 0) > 0:
            return PRESET_NORMAL
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            "timer_mode": self.coordinator.data.get("timer_mode", False),
            "raw_speed": self.coordinator.data.get("speed"),
        }

    # ------------------------------------------------------------------
    # Commands
    # ------------------------------------------------------------------

    async def _async_set_speed(self, target: int) -> None:
        """Bring the unit to ``target``: over Modbus if possible, else the web page."""
        current = self.coordinator.data.get("speed", 0)
        if self.coordinator.modbus is not None:
            try:
                await self.coordinator.async_write_register(
                    REG_SPEED_SETPOINT, target, retry=False
                )
                return
            except PureModbusError as err:
                _LOGGER.debug("Setting the speed over the web page instead: %s", err)
        await self.coordinator.api.set_speed(target, current)
        await self.coordinator.async_request_refresh()

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        if self.coordinator.modbus is not None:
            await self._async_set_preset_mode_modbus(preset_mode)
            return
        if preset_mode == PRESET_BOOST:
            await self.coordinator.api.boost()
        elif preset_mode == PRESET_NORMAL:
            # Exit boost/timer mode: turn off then back on
            current = self.coordinator.data.get("speed", 0)
            if self.coordinator.data.get("timer_mode"):
                await self.coordinator.api.set_speed(SPEED_OFF, current)
                await self.coordinator.async_request_refresh()
                await self.coordinator.api.set_speed(SPEED_MIN, SPEED_OFF)
        await self.coordinator.async_request_refresh()

    async def _async_set_preset_mode_modbus(self, preset_mode: str) -> None:
        data = self.coordinator.data
        if preset_mode == PRESET_BOOST:
            await self._async_write_register(
                REG_BOOST_TIMER, DEFAULT_BOOST_SECONDS, store=False
            )
        elif preset_mode == PRESET_SCHEDULE:
            await self._async_write_register(REG_SPEED_SETPOINT, SPEED_SETPOINT_TIMER)
        elif preset_mode == PRESET_NORMAL:
            if data.get("boost_remaining"):
                await self._async_write_register(REG_BOOST_TIMER, 0, store=False)
            if not SPEED_MIN <= (data.get("speed") or 0) <= SPEED_MAX:
                await self._async_write_register(REG_SPEED_SETPOINT, self._last_speed)

    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        if preset_mode is not None:
            await self.async_set_preset_mode(preset_mode)
            return
        target = percentage if percentage is not None else self._last_speed

        # Clamp to valid range
        target = max(SPEED_MIN, min(SPEED_MAX, target))

        await self._async_set_speed(target)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._async_set_speed(SPEED_OFF)

    async def async_set_percentage(self, percentage: int) -> None:
        percentage = int(round(percentage))  # ensure integer, no floats

        if percentage == 0:
            await self._async_set_speed(SPEED_OFF)
        else:
            await self._async_set_speed(max(SPEED_MIN, min(SPEED_MAX, percentage)))
