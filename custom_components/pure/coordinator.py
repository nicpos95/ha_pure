"""DataUpdateCoordinator for the Pure VMC VMC integration."""
from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import PureApi, PureApiError
from .const import DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)


class PureCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Single coordinator shared by all Pure VMC entities."""

    def __init__(self, hass: HomeAssistant, api: PureApi) -> None:
        self.api = api
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch all data from the device in one go."""
        try:
            return await self.api.get_all()
        except PureApiError as err:
            raise UpdateFailed(f"Error communicating with Pure VMC: {err}") from err
