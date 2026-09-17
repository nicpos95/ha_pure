"""Setting the integration up inside Home Assistant."""
from __future__ import annotations

from unittest.mock import patch

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.pure.const import CONF_HOST, CONF_MODBUS, DOMAIN
from custom_components.pure.modbus import PureModbus

from .conftest import WEB_PAGES, FakePanel

HOST = "127.0.0.1"


def _mock_web_pages(aioclient_mock: AiohttpClientMocker) -> None:
    for path, html in WEB_PAGES.items():
        aioclient_mock.get(f"http://{HOST}{path}", text=html)


def _modbus_on(panel: FakePanel):
    """Point the integration's Modbus client at the fake panel's port."""
    return patch(
        "custom_components.pure.PureModbus",
        side_effect=lambda host: PureModbus(host, panel.port),
    )


@pytest.mark.enable_socket
async def test_setup_over_modbus(
    hass: HomeAssistant,
    panel: FakePanel,
    aioclient_mock: AiohttpClientMocker,
    socket_enabled,
) -> None:
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_HOST: HOST})
    entry.add_to_hass(hass)
    with _modbus_on(panel):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    # State came from the registers, and the web server was left alone
    assert aioclient_mock.call_count == 0
    assert hass.states.get("sensor.pure_vmc_external_temperature").state == "29.7"
    assert hass.states.get("binary_sensor.pure_vmc_filter").state == "on"
    assert hass.states.get("binary_sensor.pure_vmc_alarm").attributes[
        "active_alarms"
    ] == ["filter"]
    assert hass.states.get("fan.pure_vmc_ventilation").state == "off"

    # Modbus-only entities
    assert hass.states.get("sensor.pure_vmc_fan_run_hours").state == "0"
    assert hass.states.get("sensor.pure_vmc_supply_fan_speed").state == "0"
    assert hass.states.get("sensor.pure_vmc_operating_mode").state == "off"
    assert hass.states.get("select.pure_vmc_season").state == "summer"
    # This unit's bypass is not a "universal" one: its mode is shown, not offered
    assert hass.states.get("sensor.pure_vmc_bypass_mode").state == "auto"
    assert hass.states.get("select.pure_vmc_bypass_mode") is None
    assert hass.states.get("number.pure_vmc_temperature_setpoint").state == "26.0"
    assert hass.states.get("number.pure_vmc_boost_timer").state == "0"
    assert (
        hass.states.get("sensor.pure_vmc_supply_fan_speed").attributes[
            "unit_of_measurement"
        ]
        == "rpm"
    )
    assert hass.states.get("sensor.pure_vmc_filter_alarm_threshold").state == "2000"
    assert hass.states.get("binary_sensor.pure_vmc_anti_frost").state == "off"
    assert hass.states.get("binary_sensor.pure_vmc_fan_fault").state == "off"

    device = dr.async_get(hass).async_get_device({(DOMAIN, entry.entry_id)})
    assert device is not None and device.sw_version == "25.01.09.00"

    assert await hass.config_entries.async_unload(entry.entry_id)


@pytest.mark.enable_socket
async def test_modbus_outage_falls_back_to_web(
    hass: HomeAssistant,
    panel: FakePanel,
    aioclient_mock: AiohttpClientMocker,
    socket_enabled,
) -> None:
    _mock_web_pages(aioclient_mock)
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_HOST: HOST})
    entry.add_to_hass(hass)
    with _modbus_on(panel):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    await panel.stop()
    coordinator = hass.data[DOMAIN][entry.entry_id]
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    assert aioclient_mock.call_count == len(WEB_PAGES)
    # Core entities keep working from the web pages...
    assert hass.states.get("sensor.pure_vmc_external_temperature").state == "29.7"
    assert hass.states.get("binary_sensor.pure_vmc_filter").state == "on"
    # ...while what only Modbus knows becomes unknown rather than stale.
    assert hass.states.get("sensor.pure_vmc_fan_run_hours").state == "unknown"

    await panel.start()  # so the fixture can stop it again


async def test_setup_without_modbus(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    _mock_web_pages(aioclient_mock)
    entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_HOST: HOST}, options={CONF_MODBUS: False}
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.pure_vmc_external_temperature").state == "29.7"
    assert hass.states.get("binary_sensor.pure_vmc_filter").attributes[
        "alarm_banner"
    ] == "DirtyFilters"
    assert hass.states.get("sensor.pure_vmc_fan_run_hours") is None
    assert hass.states.get("binary_sensor.pure_vmc_fan_fault") is None
    assert hass.states.get("select.pure_vmc_season") is None
    assert hass.states.get("number.pure_vmc_boost_timer") is None
    fan = hass.states.get("fan.pure_vmc_ventilation")
    assert fan.attributes["preset_modes"] == ["normal", "boost"]


async def test_options_flow(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    _mock_web_pages(aioclient_mock)
    entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_HOST: HOST}, options={CONF_MODBUS: False}
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["step_id"] == "init"
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_MODBUS: False}
    )
    assert result["type"] == "create_entry"
    assert entry.options == {CONF_MODBUS: False}
