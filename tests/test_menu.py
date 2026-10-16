"""The web Installer menu driver, against a fake of the panel's menu state machine."""
from __future__ import annotations

import re
from unittest.mock import patch

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.pure.menu import PureMenu, PureMenuCodeRejected, PureMenuError

from .fake_menu import HOME, INSTALLER, PASSWORD, FakeMenu

HOST = "127.0.0.1"


@pytest.fixture(autouse=True)
def no_request_spacing():
    with patch("custom_components.pure.menu.REQUEST_INTERVAL", 0):
        yield


def mock_menu(aioclient_mock: AiohttpClientMocker, fake: FakeMenu) -> None:
    aioclient_mock.get(re.compile(rf"http://{HOST}/(index\.html|cmd_sel)"), side_effect=fake.handle)
    aioclient_mock.post(f"http://{HOST}/menu.html", side_effect=fake.handle)


def _filter_presses(fake: FakeMenu) -> list[str]:
    return [p for p in fake.presses if p.endswith("0F04")]


async def test_raise_and_lower(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> None:
    fake = FakeMenu(code="1234", filter_hours=4000)
    mock_menu(aioclient_mock, fake)
    menu = PureMenu(HOST, async_get_clientsession(hass), "1234")

    assert await menu.set_filter_hours(15000) == 15000
    # Ten-step presses while far off, single steps for the rest
    assert _filter_presses(fake) == ["iic0F04", "iic0F04", "inc0F04", "inc0F04"]
    assert fake.screen == HOME  # left on the home screen, menu locked again

    fake.presses.clear()
    assert await menu.set_filter_hours(4500) == 4500
    assert _filter_presses(fake) == ["ddc0F04", "ddc0F04", "dec0F04"]

    # Already there: nothing is pressed on the row
    fake.presses.clear()
    assert await menu.set_filter_hours(4500) == 4500
    assert _filter_presses(fake) == []


async def test_from_a_menu_left_open(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> None:
    # index.html does not move the server off the screen it is on
    fake = FakeMenu(code="1234")
    fake.screen = INSTALLER
    mock_menu(aioclient_mock, fake)
    menu = PureMenu(HOST, async_get_clientsession(hass), "1234")
    assert await menu.set_filter_hours(4500) == 4500
    assert fake.screen == HOME


async def test_code_with_leading_zero(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> None:
    fake = FakeMenu(code="0815")
    mock_menu(aioclient_mock, fake)
    menu = PureMenu(HOST, async_get_clientsession(hass), "0815")
    assert await menu.set_filter_hours(4500) == 4500


async def test_half_typed_code_is_cleared(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> None:
    fake = FakeMenu(code="1234")
    fake.keeps_typed_digits = True
    fake.screen, fake.digits = PASSWORD, [5, 6]
    mock_menu(aioclient_mock, fake)
    menu = PureMenu(HOST, async_get_clientsession(hass), "1234")
    assert await menu.set_filter_hours(4500) == 4500


async def test_wrong_code(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> None:
    fake = FakeMenu(code="1234")
    mock_menu(aioclient_mock, fake)
    menu = PureMenu(HOST, async_get_clientsession(hass), "9999")
    with pytest.raises(PureMenuCodeRejected):
        await menu.set_filter_hours(4500)
    assert fake.filter_hours == 4000
    assert fake.screen == HOME


async def test_no_filter_hours_row(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> None:
    # The Installer menu has no "Ore Filtri" row when the filter alarm is not hours-based
    fake = FakeMenu(code="1234")
    fake.filter_row = False
    mock_menu(aioclient_mock, fake)
    menu = PureMenu(HOST, async_get_clientsession(hass), "1234")
    with pytest.raises(PureMenuError, match="not set to count run hours"):
        await menu.set_filter_hours(4500)
    assert fake.screen == HOME


async def test_invalid_target_sends_nothing(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> None:
    fake = FakeMenu(code="1234")
    mock_menu(aioclient_mock, fake)
    menu = PureMenu(HOST, async_get_clientsession(hass), "1234")
    with pytest.raises(ValueError):
        await menu.set_filter_hours(4321)
    assert fake.requests == 0
    with pytest.raises(ValueError):
        PureMenu(HOST, async_get_clientsession(hass), "12")
