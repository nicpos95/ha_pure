"""Button entities for Pure VMC (the filter-change reset, through the web Installer menu)."""
from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_FILTER_INTERVAL, DEFAULT_FILTER_INTERVAL, DOMAIN
from .coordinator import PureCoordinator
from .entity_base import PureEntity
from .menu import FILTER_HOURS_MAX, FILTER_HOURS_STEP


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: PureCoordinator = hass.data[DOMAIN][entry.entry_id]
    if coordinator.menu is None:
        return
    async_add_entities([PureFiltersReplacedButton(coordinator, entry.entry_id)])


def next_filter_threshold(run_hours: int, interval: int) -> int:
    """Run hours now plus the interval, rounded up to the unit's 500 h steps.

    The manual's reset: "Ore filtri = Ore vent. + ore per nuovo allarme".
    """
    target = -(-(run_hours + interval) // FILTER_HOURS_STEP) * FILTER_HOURS_STEP
    return min(target, FILTER_HOURS_MAX)


class PureFiltersReplacedButton(PureEntity, ButtonEntity):
    """Press after changing the filters: the next alarm comes after one interval."""

    _attr_translation_key = "filters_replaced"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_icon = "mdi:air-filter"

    def __init__(self, coordinator: PureCoordinator, entry_id: str) -> None:
        super().__init__(coordinator, entry_id)
        self._attr_unique_id = f"{entry_id}_filters_replaced"

    async def async_press(self) -> None:
        interval = int(
            self.coordinator.config_entry.options.get(
                CONF_FILTER_INTERVAL, DEFAULT_FILTER_INTERVAL
            )
        )
        await self.coordinator.async_refresh()  # the run hours as of now
        await self._async_set_filter_hours(
            next_filter_threshold(int(self.coordinator.data["fan_hours"]), interval)
        )
