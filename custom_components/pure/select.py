"""Select entities for Pure VMC (season and bypass mode, over Modbus)."""
from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import PureCoordinator
from .entity_base import PureEntity
from .modbus import (
    BYPASS_MODE_MASK,
    BYPASS_MODE_SHIFT,
    BYPASS_MODES,
    REG_PARAMETER_FLAGS,
    SEASON_MASK,
    SEASONS,
)


@dataclass(frozen=True, kw_only=True)
class PureSelectDescription(SelectEntityDescription):
    """A setting stored in a few bits of the PARAMETER_FLAGS register."""

    values: dict[int, str]
    mask: int
    shift: int = 0


SELECTS: tuple[PureSelectDescription, ...] = (
    PureSelectDescription(
        key="season",
        translation_key="season",
        icon="mdi:sun-snowflake-variant",
        values=SEASONS,
        mask=SEASON_MASK,
    ),
    PureSelectDescription(
        key="bypass_mode",
        translation_key="bypass_mode",
        icon="mdi:valve",
        values=BYPASS_MODES,
        mask=BYPASS_MODE_MASK,
        shift=BYPASS_MODE_SHIFT,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: PureCoordinator = hass.data[DOMAIN][entry.entry_id]
    # These settings sit behind the menu screens of the web interface, so they
    # are only reachable over Modbus.
    if coordinator.modbus is None:
        return
    async_add_entities(
        PureSelect(coordinator, entry.entry_id, description)
        for description in SELECTS
        # The unit ignores the bypass mode unless its bypass is a "universal"
        # one; it is then shown as a sensor instead of a control that does nothing.
        if description.key != "bypass_mode"
        or coordinator.data.get("bypass_mode_selectable")
    )


class PureSelect(PureEntity, SelectEntity):
    """One of the unit's mode settings."""

    entity_description: PureSelectDescription
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self,
        coordinator: PureCoordinator,
        entry_id: str,
        description: PureSelectDescription,
    ) -> None:
        super().__init__(coordinator, entry_id)
        self.entity_description = description
        self._attr_unique_id = f"{entry_id}_{description.key}_select"
        self._attr_options = list(description.values.values())

    @property
    def current_option(self) -> str | None:
        return self.coordinator.data.get(self.entity_description.key)

    async def async_select_option(self, option: str) -> None:
        description = self.entity_description
        raw = next(raw for raw, name in description.values.items() if name == option)
        await self._async_write_register(
            REG_PARAMETER_FLAGS, raw << description.shift, description.mask
        )
