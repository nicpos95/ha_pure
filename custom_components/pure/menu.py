"""Driver for the panel's web Installer menu, for the one setting Modbus will not change.

The filter-alarm threshold ("Ore Filtri") is readable over Modbus (register 24) but
the panel ignores Modbus writes to it, so it is changed the way an installer would:
through the Installer menu of the web interface, behind the installer code.

That interface is a server-side state machine mirrored from the touch panel:

- every link means "select item II on the *current* screen" (``cmd_selSSIImenu.html``,
  SS = screen, II = item; item 80 is Home and 82 is Menu on every screen). A link
  that is not on the current screen does nothing and returns the current screen, so
  the driver checks where it really is after every step instead of trusting a URL;
- the code is typed digit by digit with +/- buttons: the first digit has to be
  "armed" with a press before it counts, each select commits a digit and arms the
  next one at 0, and the fourth commit submits;
- every parameter row has +/- buttons (one step) and double ones (ten steps); the
  page returned by a press already shows the new value;
- the server is tiny and drops requests that come too fast.

Every button press here is a change made "from the web page", after which the unit
refuses Modbus writes for about a minute (see ``modbus.PureModbusWriteIgnored``).

No Home Assistant import, so it can be exercised on its own.
"""
from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass

import aiohttp
from yarl import URL

REQUEST_INTERVAL = 0.5  # seconds between requests; the panel drops faster ones
REQUEST_TIMEOUT = 10  # seconds
MAX_PRESSES = 60  # per value change, a guard against a row that stops moving

HOME_ITEM = "80"
MENU_ITEM = "82"
# Main menu items (screen 02) by label, Italian and English panels
INSTALLER_LABELS = ("installatore", "installer")

PASSWORD_ROW = "0104"  # the code field on the password screen
PASSWORD_SELECT = "sel0103"

# The filter-hours row: its label, then the value (5 digits)
FILTER_ROW_PATTERN = re.compile(r"^(ore\s*filtri|filters?\s*hours?)\s*(\d+)$", re.IGNORECASE)
FILTER_HOURS_STEP = 500  # one press of + or -
FILTER_HOURS_BIG_STEP = 5000  # one press of the double arrows
FILTER_HOURS_MAX = 99500

_ROW_RE = re.compile(r"<tr", re.IGNORECASE)
_PRE_RE = re.compile(r"<pre[^>]*>(.*?)</pre>", re.IGNORECASE | re.DOTALL)
_BUTTON_RE = re.compile(r'name="([a-z]{3}[0-9A-Fa-f]{4})"')
_LINK_RE = re.compile(r'<a href="(cmd_sel([0-9A-Fa-f]{2})([0-9A-Fa-f]{2})menu\.html)">([^<]*)</a>')
_TAG_RE = re.compile(r"<[^>]+>")


class PureMenuError(Exception):
    """Raised when the web menu does not behave as expected."""


class PureMenuCodeRejected(PureMenuError):
    """Raised when the panel does not accept the installer code."""


@dataclass
class _Page:
    """One screen of the web interface, as returned by the panel."""

    html: str

    @property
    def rows(self) -> list[tuple[str, list[str]]]:
        """(text, button names) for every row that shows some text."""
        out = []
        for row in _ROW_RE.split(self.html):
            pre = _PRE_RE.search(row)
            if not pre:
                continue
            text = " ".join(_TAG_RE.sub("", pre.group(1)).split())
            if text:
                out.append((text, sorted(set(_BUTTON_RE.findall(row)))))
        return out

    @property
    def links(self) -> dict[str, str]:
        """Link label -> URL path."""
        return {label.strip(): href for href, _s, _i, label in _LINK_RE.findall(self.html)}

    def link_to_item(self, item: str) -> str | None:
        for href, _screen, link_item, _label in _LINK_RE.findall(self.html):
            if link_item.upper() == item:
                return href
        return None

    @property
    def password_field(self) -> str | None:
        """The code field ("----" when empty) on the password screen, else None."""
        if f"inc{PASSWORD_ROW}" not in self.html:
            return None
        pres = [" ".join(_TAG_RE.sub("", p).split()) for p in _PRE_RE.findall(self.html)]
        return pres[-1] if pres else ""

    def installer_link(self) -> str | None:
        for label, href in self.links.items():
            if label.lower() in INSTALLER_LABELS:
                return href
        return None

    def filter_hours_row(self) -> tuple[int, str] | None:
        """(value, row id) of the filter-hours row, when it is on this screen."""
        for text, buttons in self.rows:
            match = FILTER_ROW_PATTERN.match(text)
            if not match:
                continue
            for name in buttons:
                if name.startswith("inc"):
                    return int(match.group(2)), name[3:]
        return None


class PureMenu:
    """Changes the filter-alarm threshold through the panel's Installer menu."""

    def __init__(
        self,
        host: str,
        session: aiohttp.ClientSession,
        installer_code: str,
        request_interval: float | None = None,
    ) -> None:
        if not re.fullmatch(r"\d{4}", installer_code):
            raise ValueError("The installer code is four digits")
        self._base = URL(host if "://" in host else f"http://{host}")
        self._session = session
        self._code = installer_code
        self._interval = request_interval

    async def set_filter_hours(self, target: int) -> int:
        """Set the threshold to ``target`` hours; return the value the panel shows.

        Leaves the web interface on its home screen in any case.
        """
        if target % FILTER_HOURS_STEP or not 0 <= target <= FILTER_HOURS_MAX:
            raise ValueError(
                f"The threshold is a multiple of {FILTER_HOURS_STEP} h up to {FILTER_HOURS_MAX} h"
            )
        page = await self._open_installer()
        try:
            return await self._move_filter_hours(page, target)
        finally:
            await self._go_home()

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------

    async def _request(self, path: str, button: str | None = None, _hops: int = 0) -> _Page:
        await asyncio.sleep(REQUEST_INTERVAL if self._interval is None else self._interval)
        url = self._base.with_path("/" + path.lstrip("/"))
        try:
            if button is None:
                response = await self._session.get(
                    url, allow_redirects=False, timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)
                )
            else:
                response = await self._session.post(
                    self._base.with_path("/menu.html"),
                    data=f"{button}.x=1&{button}.y=1",
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                    allow_redirects=False,
                    timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT),
                )
            async with response:
                if response.status in (301, 302, 303, 307, 308):
                    # The panel's own HTTPS is broken: follow its redirects over HTTP
                    if _hops >= 3:
                        raise PureMenuError(f"Too many redirects from {url.path}")
                    location = URL(response.headers.get("Location", "/"))
                    return await self._request(location.path, _hops=_hops + 1)
                if response.status != 200:
                    raise PureMenuError(f"The panel answered {response.status} for {url.path}")
                return _Page(await response.text(encoding="cp1252", errors="replace"))
        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            raise PureMenuError(f"Web menu request to {url.path} failed: {err}") from err

    async def _to_main_menu(self) -> _Page:
        """Reach the main menu (screen 02) from wherever the panel is."""
        page = await self._request("index.html")
        for _ in range(3):
            menu = page.link_to_item(MENU_ITEM) or page.links.get("Menu")
            if menu is None:
                break
            page = await self._request(menu)
            if page.installer_link() is not None:
                return page
        raise PureMenuError("Could not reach the main menu of the web interface")

    async def _go_home(self) -> None:
        """Back to the home screen through the screens' own links (re-locks the menu)."""
        try:
            page = await self._to_main_menu()
            home = page.link_to_item(HOME_ITEM)
            if home is not None:
                await self._request(home)
        except PureMenuError:
            pass

    async def _open_installer(self) -> _Page:
        main = await self._to_main_menu()
        link = main.installer_link()
        assert link is not None
        page = await self._request(link)
        if page.password_field is None:
            return page  # already open
        if page.password_field.strip("-"):
            # Someone left a code half typed: completing it bounces back to an empty field
            for _ in range(4):
                page = await self._request("menu.html", PASSWORD_SELECT)
                if page.password_field is None or not page.password_field.strip("-"):
                    break
            page = await self._request((await self._to_main_menu()).installer_link() or link)
            if page.password_field is None:
                return page
            if page.password_field.strip("-"):
                raise PureMenuError("The installer code field could not be cleared")
        for position, char in enumerate(self._code):
            digit = int(char)
            if position == 0 and digit == 0:
                page = await self._request("menu.html", f"dec{PASSWORD_ROW}")  # arms it at 0
            for _ in range(digit):
                page = await self._request("menu.html", f"inc{PASSWORD_ROW}")
            page = await self._request("menu.html", PASSWORD_SELECT)
        if page.password_field is not None:
            await self._go_home()
            raise PureMenuCodeRejected("The panel did not accept the installer code")
        return page

    async def _move_filter_hours(self, page: _Page, target: int) -> int:
        row = page.filter_hours_row()
        for _ in range(12):  # the row may sit lower down the list
            if row is not None:
                break
            down = next((b for _t, bs in page.rows for b in bs if b.startswith("sdw")), None)
            if down is None:
                break
            page = await self._request("menu.html", down)
            row = page.filter_hours_row()
        if row is None:
            raise PureMenuError(
                "The Installer menu has no filter-hours row: the filter alarm is not "
                "set to count run hours (Factory menu)"
            )
        value, row_id = row
        for _ in range(MAX_PRESSES):
            difference = target - value
            if difference == 0:
                return value
            if abs(difference) >= FILTER_HOURS_BIG_STEP:
                button = "iic" if difference > 0 else "ddc"
            else:
                button = "inc" if difference > 0 else "dec"
            page = await self._request("menu.html", f"{button}{row_id}")
            moved = page.filter_hours_row()
            if moved is None or moved[0] == value:
                raise PureMenuError(
                    f"The filter-hours value stopped moving at {value} h (asked for {target} h)"
                )
            value = moved[0]
        raise PureMenuError(f"Gave up moving the filter-hours value at {value} h")
