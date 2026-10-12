"""A fake of the panel's web menu: a server-side state machine, like the real one.

Modelled on pages captured from a Pure 250: links are "item II on screen SS" and do
nothing on any other screen; index.html serves the home page without moving the
server off the screen it is on; the code is typed digit by digit (the first digit
must be armed, each select commits one and arms the next at 0); every row has
+/- (one step) and double +/- (ten steps); the page returned by a press shows the
new value.
"""
from __future__ import annotations

import re

from pytest_homeassistant_custom_component.test_util.aiohttp import (
    AiohttpClientMockResponse,
)

HOME, MAIN, PASSWORD, INSTALLER = "00", "02", "01", "0F"
MAIN_ITEMS = {"01": "Stato", "02": "Allarmi", "03": "Programma", "04": "Orologio",
              "05": "Parametri", "06": "Installatore", "07": "Fabbrica"}


def _link(screen: str, item: str, label: str) -> str:
    return f'<a href="cmd_sel{screen}{item}menu.html">{label}</a>'


def _row(text: str, row_id: str | None = None) -> str:
    buttons = (
        "".join(f'<input type="image" src="x.gif" name="{op}{row_id}"/>' for op in ("dec", "ddc", "iic", "inc"))
        if row_id
        else ""
    )
    return (
        f'<tr><td style="height:45px"><pre style="font-weight: bold">{text}</pre></td>'
        f'<td style="text-align:right"><form action=menu.html method="post">{buttons}</form></td></tr>'
    )


class FakeMenu:
    def __init__(self, code: str = "1234", filter_hours: int = 4000, panel=None) -> None:
        self.code = code
        self.filter_hours = filter_hours
        self.filter_row = True  # False: filter alarm not hours-based (no "Ore Filtri" row)
        self.keeps_typed_digits = False  # True: a half-typed code is still there on return
        self.panel = panel  # a FakePanel: the threshold is mirrored into its register 24
        self.screen = HOME
        self.digits: list[int | None] = []
        self.presses: list[str] = []
        self.requests = 0

    # -- pages --------------------------------------------------------------

    def _page(self) -> str:
        if self.screen == HOME:
            return f"<html><body>{_link(HOME, '00', 'Menu')}<iframe src=\"ifspeed_sp.html\"></iframe></body></html>"
        if self.screen == MAIN:
            links = _link(MAIN, "80", "Home") + "".join(_link(MAIN, i, l) for i, l in MAIN_ITEMS.items())
            return f"<html><body><h3>{links}</h3><table>{''.join(_row(l) for l in MAIN_ITEMS.values())}</table></body></html>"
        if self.screen == PASSWORD:
            field = "".join("*" if d == "*" else "-" if d is None else str(d) for d in self._field())
            links = _link(PASSWORD, "80", "Home") + _link(PASSWORD, "82", "Menu")
            return (
                f"<html><body><h3>{links} &gt; Installatore</h3><table>"
                f"{_row('Unita Ver.4.31.1')}<tr><td><pre> </pre></td></tr>"
                f'<tr><td><form><input type="submit" value="Componi Password" name="sel0103"/></form></td></tr>'
                f"{_row(field + ' ', '0104')}</table></body></html>"
            )
        links = _link(INSTALLER, "80", "Home") + _link(INSTALLER, "82", "Menu")
        rows = [_row("Lingua        IT", "0F01"), _row("Auto1    Nessuno", "0F02")]
        if self.filter_row:
            rows.append(_row(f"Ore Filtri {self.filter_hours:05d}", "0F04"))
        rows.append(_row("Vel.Max     100%", "0F05"))
        return f"<html><body><h3>{links} &gt; Installatore</h3><table>{''.join(rows)}</table></body></html>"

    def _field(self) -> list:
        committed = ["*"] * (len(self.digits) - 1) if self.digits else []
        current = self.digits[-1] if self.digits else None
        return (committed + [current] + [None] * 4)[:4] if self.digits else [None] * 4

    # -- behaviour ----------------------------------------------------------

    def _select(self, screen: str, item: str) -> None:
        if screen != self.screen:
            return  # a link that is not on the current screen does nothing
        if item == "80":
            self.screen = HOME
        elif item == "82" and self.screen != HOME:
            self.screen = MAIN
        elif self.screen == HOME and item == "00":
            self.screen = MAIN
        elif self.screen == MAIN and item == "06":
            self.screen = PASSWORD
            if not self.keeps_typed_digits:
                self.digits = []

    def _press(self, button: str) -> None:
        self.presses.append(button)
        op, target = button[:3], button[3:]
        if self.screen == PASSWORD and target == "0104" and op in ("inc", "dec"):
            if not self.digits:
                self.digits = [None]
            current = self.digits[-1]
            if current is None:
                self.digits[-1] = 1 if op == "inc" else 0
            else:
                self.digits[-1] = (current + (1 if op == "inc" else -1)) % 10
        elif self.screen == PASSWORD and button == "sel0103":
            if not self.digits or self.digits[-1] is None:
                self.screen, self.digits = MAIN, []  # an unarmed field submits nothing
            elif len(self.digits) < 4:
                self.digits.append(0)  # commit, and arm the next digit at 0
            else:
                typed = "".join(str(d) for d in self.digits)
                self.digits = []
                if typed == self.code:
                    self.screen = INSTALLER
        elif self.screen == INSTALLER and target == "0F04" and self.filter_row:
            step = {"inc": 500, "dec": -500, "iic": 5000, "ddc": -5000}.get(op, 0)
            self.filter_hours = min(max(self.filter_hours + step, 0), 99500)
            if self.panel is not None:
                self.panel.registers[24] = self.filter_hours // 500

    async def handle(self, method: str, url, data) -> AiohttpClientMockResponse:
        self.requests += 1
        path = url.path
        if method.upper() == "POST":
            self._press(re.match(r"([a-z]{3}[0-9A-Fa-f]{4})\.x=", data).group(1))
        elif (match := re.fullmatch(r"/cmd_sel([0-9A-F]{2})([0-9A-F]{2})menu\.html", path)):
            self._select(*match.groups())
        elif path == "/index.html":
            return AiohttpClientMockResponse(method, url, text=self._page_home())
        return AiohttpClientMockResponse(method, url, text=self._page())

    def _page_home(self) -> str:
        # The home page, served without moving the server off its current screen
        return f"<html><body>{_link(HOME, '00', 'Menu')}</body></html>"
