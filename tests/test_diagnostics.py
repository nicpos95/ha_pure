"""The diagnostics download."""
from __future__ import annotations

import pytest
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.pure.const import CONF_HOST, DOMAIN
from custom_components.pure.diagnostics import async_get_config_entry_diagnostics

from .conftest import FakePanel
from .test_init import HOST, _modbus_on


@pytest.mark.enable_socket
async def test_diagnostics(hass: HomeAssistant, panel: FakePanel, socket_enabled) -> None:
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_HOST: HOST})
    entry.add_to_hass(hass)
    with _modbus_on(panel):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    diagnostics = await async_get_config_entry_diagnostics(hass, entry)
    assert diagnostics["modbus"] is True
    assert diagnostics["entry"]["data"][CONF_HOST] == "**REDACTED**"
    assert diagnostics["registers"]["90"] == 16
    assert diagnostics["registers"]["38"] == 0  # the extra, undecoded block
    assert diagnostics["data"]["filter_dirty"] is True
