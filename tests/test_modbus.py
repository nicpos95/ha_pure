"""The Modbus client and the register decoder, without Home Assistant."""
from __future__ import annotations

import pytest

from custom_components.pure.modbus import (
    PureModbus,
    PureModbusError,
    PureModbusWriteIgnored,
    decode_registers,
)

from .conftest import LIVE_REGISTERS, FakePanel


def _registers(**overrides: int) -> dict[int, int]:
    registers = {number: 0 for number in range(1, 100)}
    registers.update(LIVE_REGISTERS)
    registers.update({int(key[1:]): value for key, value in overrides.items()})
    return registers


@pytest.mark.enable_socket
async def test_read_registers(panel: FakePanel, socket_enabled) -> None:
    client = PureModbus("127.0.0.1", panel.port)
    registers = await client.read_registers()
    assert registers[81] == 297
    assert registers[90] == 16
    assert panel.requests == 3  # three blocks, one connection


@pytest.mark.enable_socket
async def test_connection_refused(socket_enabled, unused_tcp_port: int) -> None:
    client = PureModbus("127.0.0.1", unused_tcp_port)
    assert await client.test_connection() is False
    with pytest.raises(PureModbusError):
        await client.read_registers()


@pytest.mark.enable_socket
async def test_write_register(panel: FakePanel, socket_enabled) -> None:
    client = PureModbus("127.0.0.1", panel.port)
    assert await client.write_register(51, 30) == 30
    # The panel clamps: accepted, just not to the value that was asked for
    assert await client.write_register(51, 10) == 20
    # Only the masked bits change (season is bits 0-1 of register 20)
    assert await client.write_register(20, 1, mask=0b11) == 33
    # Writing what is already there is not a refusal
    assert await client.write_register(20, 1, mask=0b11) == 33

    # Each change was stored: set-points with bit 15, configuration with bit 14,
    # and the notice flags already in register 5 were left as they were
    assert panel.stored == [0b10, 0b10, 0b01]
    assert panel.registers[5] == 17

    # A value that is temporary by nature is written without being stored
    assert await client.write_register(53, 600, store=False) == 600
    assert panel.stored == [0b10, 0b10, 0b01]


@pytest.mark.enable_socket
async def test_write_ignored_during_lockout(panel: FakePanel, socket_enabled) -> None:
    client = PureModbus("127.0.0.1", panel.port)
    panel.locked_out = True
    with pytest.raises(PureModbusWriteIgnored):
        await client.write_register(51, 30)
    assert panel.registers[51] == 0
    assert panel.stored == []


def test_decode_live_capture() -> None:
    data = decode_registers(_registers())
    assert data["speed"] == 0
    assert data["operating_mode"] == "off"
    assert data["temp_external"] == 29.7
    assert data["temp_setpoint"] == 26.0
    assert data["filter_dirty"] is True
    assert data["alarm_active"] is True
    assert data["active_alarms"] == ["filter"]
    assert data["bypass"] is False
    assert data["season"] == "summer"
    assert data["bypass_mode"] == "auto"
    assert data["fan_hours"] == 0
    assert data["filter_max_hours"] == 2000
    # This unit leaves CONFIG_FLAGS_1 at 0 and still reports RPM
    assert data["fan_speed_is_rpm"] is True
    assert data["sw_version"] == "25.01.09.00"


def test_decode_running_unit() -> None:
    data = decode_registers(
        _registers(
            r7=2 << 8, r20=0b1001, r51=101, r52=40, r81=0xFFCE, r86=0b10001,
            r87=1480, r88=1390, r90=0, r95=1, r96=5,
        )
    )
    assert data["temp_external"] == -5.0
    assert data["temp_setpoint"] is None  # <= 48 means "off"
    assert data["timer_mode"] is True
    assert data["operating_mode"] == "schedule"
    assert data["bypass"] is True
    assert data["anti_frost"] is True
    assert data["fan_speed_is_rpm"] is True
    assert data["fan_supply_speed"] == 1480
    assert data["fan_hours"] == 65541
    assert data["season"] == "winter"
    assert data["bypass_mode"] == "on"
    assert data["alarm_active"] is False
    # An explicitly non-tacho fan alarm means the speeds are percentages
    assert decode_registers(_registers(r7=1 << 8))["fan_speed_is_rpm"] is False


def test_decode_faults_and_boost() -> None:
    data = decode_registers(_registers(r53=600, r90=0b110100010, r97=0b11))
    assert data["operating_mode"] == "boost"
    assert data["boost_remaining"] == 600
    # A failed probe must read as unknown, not as its garbage value
    assert data["temp_external"] is None
    assert data["temp_inlet"] is None
    assert data["temp_return"] == 29.3
    assert data["fault_fans"] is True
    assert data["fault_communication"] is True
    assert data["fault_configuration"] is True
    assert data["fault_anti_frost"] is True
    assert data["filter_dirty"] is False
