"""Fan entity for Pure VMC."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, SPEED_MAX, SPEED_MIN, SPEED_OFF, SPEED_TIMER_MODE
from .coordinator import PureCoordinator
from .entity_base import PureEntity

_LOGGER = logging.getLogger(__name__)

PRESET_NORMAL = "normal"
PRESET_BOOST = "boost"
PRESET_MODES = [PRESET_NORMAL, PRESET_BOOST]


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
        if speed == SPEED_TIMER_MODE:
            # Timer mode: we report 100 so automations using percentage
            # don't get confused by the out-of-range 101 value.
            # The timer_mode attribute on the speed sensor is the precise indicator.
            return 100
        return speed


    @property
    def preset_mode(self) -> str | None:
        """Return current preset mode."""
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

    async def async_set_preset_mode(self, preset_mode: str) -> None:
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

    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        current = self.coordinator.data.get("speed", 0)
        target = percentage if percentage is not None else SPEED_MIN

        # Clamp to valid range
        target = max(SPEED_MIN, min(SPEED_MAX, target))

        await self.coordinator.api.set_speed(target, current)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        current = self.coordinator.data.get("speed", 0)
        await self.coordinator.api.set_speed(SPEED_OFF, current)
        await self.coordinator.async_request_refresh()

    async def async_set_percentage(self, percentage: int) -> None:
        current = self.coordinator.data.get("speed", 0)
        percentage = int(round(percentage))  # ensure integer, no floats

        if percentage == 0:
            await self.coordinator.api.set_speed(SPEED_OFF, current)
        else:
            target = max(SPEED_MIN, min(SPEED_MAX, percentage))
            await self.coordinator.api.set_speed(target, current)

        await self.coordinator.async_request_refresh()