"""Commands: over Modbus, with the web page as the fan's fallback."""
from __future__ import annotations

from datetime import timedelta
from unittest.mock import patch

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.pure.const import CONF_HOST, DOMAIN

from .conftest import FakePanel
from .test_init import HOST, _modbus_on

pytestmark = pytest.mark.enable_socket

FAN = "fan.pure_vmc_ventilation"


@pytest.fixture
async def entry(hass: HomeAssistant, panel: FakePanel, socket_enabled) -> MockConfigEntry:
    panel.registers[7] = 2 << 8 | 2 << 10  # tacho fans, "universal" bypass
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_HOST: HOST})
    entry.add_to_hass(hass)
    with _modbus_on(panel):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    return entry


async def _call(hass: HomeAssistant, domain: str, service: str, **data) -> None:
    await hass.services.async_call(domain, service, data, blocking=True)
    await hass.async_block_till_done()


async def test_fan_speed_over_modbus(
    hass: HomeAssistant,
    panel: FakePanel,
    entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    await _call(hass, "fan", "set_percentage", entity_id=FAN, percentage=45)
    assert panel.registers[51] == 45
    assert hass.states.get(FAN).attributes["percentage"] == 45
    assert hass.states.get(FAN).attributes["preset_mode"] == "normal"

    await _call(hass, "fan", "turn_off", entity_id=FAN)
    assert panel.registers[51] == 0

    # Turning back on returns to the last speed, in one write and no web request
    await _call(hass, "fan", "turn_on", entity_id=FAN)
    assert panel.registers[51] == 45
    assert aioclient_mock.call_count == 0


async def test_fan_presets_over_modbus(
    hass: HomeAssistant, panel: FakePanel, entry: MockConfigEntry
) -> None:
    await _call(hass, "fan", "set_percentage", entity_id=FAN, percentage=30)

    await _call(hass, "fan", "set_preset_mode", entity_id=FAN, preset_mode="boost")
    assert panel.registers[53] == 15 * 60
    assert hass.states.get(FAN).attributes["preset_mode"] == "boost"
    assert hass.states.get("number.pure_vmc_boost_timer").state == "15"

    await _call(hass, "fan", "set_preset_mode", entity_id=FAN, preset_mode="schedule")
    assert panel.registers[51] == 101
    panel.registers[53] = 0
    await hass.data[DOMAIN][entry.entry_id].async_refresh()
    assert hass.states.get(FAN).attributes["preset_mode"] == "schedule"

    await _call(hass, "fan", "set_preset_mode", entity_id=FAN, preset_mode="normal")
    assert panel.registers[51] == 30  # back to the last manual speed


async def test_fan_falls_back_to_web_during_lockout(
    hass: HomeAssistant, panel: FakePanel, entry: MockConfigEntry
) -> None:
    panel.locked_out = True
    with patch("custom_components.pure.api.PureApi.set_speed") as web_set_speed:
        await _call(hass, "fan", "set_percentage", entity_id=FAN, percentage=50)
    web_set_speed.assert_awaited_once_with(50, 0)


async def test_selects_and_numbers(
    hass: HomeAssistant, panel: FakePanel, entry: MockConfigEntry
) -> None:
    await _call(
        hass, "select", "select_option", entity_id="select.pure_vmc_season", option="winter"
    )
    assert panel.registers[20] == 33  # only bits 0-1 changed (34 -> 33)
    await _call(
        hass, "select", "select_option", entity_id="select.pure_vmc_bypass_mode", option="on"
    )
    assert panel.registers[20] == 33 | 2 << 2
    assert hass.states.get("select.pure_vmc_season").state == "winter"

    await _call(
        hass, "number", "set_value", entity_id="number.pure_vmc_temperature_setpoint", value=22.5
    )
    assert panel.registers[52] == 224  # rounded to the unit's 0.2 degree step

    await _call(hass, "number", "set_value", entity_id="number.pure_vmc_boost_timer", value=10)
    assert panel.registers[53] == 600


async def test_dropped_write_is_retried(
    hass: HomeAssistant, panel: FakePanel, entry: MockConfigEntry
) -> None:
    panel.locked_out = True
    await _call(
        hass, "select", "select_option", entity_id="select.pure_vmc_season", option="winter"
    )
    # No error for the user, nothing changed on the unit yet
    assert panel.registers[20] == 34
    assert hass.states.get("select.pure_vmc_season").state == "summer"

    # Still locked out at the first retry, accepted at the second
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=16))
    await hass.async_block_till_done(wait_background_tasks=True)
    assert panel.registers[20] == 34

    panel.locked_out = False
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=32))
    await hass.async_block_till_done(wait_background_tasks=True)
    assert panel.registers[20] == 33
    assert hass.states.get("select.pure_vmc_season").state == "winter"


async def test_newer_command_replaces_a_waiting_one(
    hass: HomeAssistant, panel: FakePanel, entry: MockConfigEntry
) -> None:
    panel.locked_out = True
    await _call(
        hass, "number", "set_value", entity_id="number.pure_vmc_temperature_setpoint", value=22
    )
    panel.locked_out = False
    await _call(
        hass, "number", "set_value", entity_id="number.pure_vmc_temperature_setpoint", value=24
    )
    assert panel.registers[52] == 240

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=16))
    await hass.async_block_till_done(wait_background_tasks=True)
    assert panel.registers[52] == 240  # the 22 degrees that was waiting is gone


async def test_unreachable_unit_is_reported(
    hass: HomeAssistant, panel: FakePanel, entry: MockConfigEntry
) -> None:
    await panel.stop()
    with pytest.raises(HomeAssistantError):
        await _call(
            hass, "select", "select_option", entity_id="select.pure_vmc_season", option="winter"
        )
    await panel.start()  # so the fixture can stop it again
