"""HTTP client for the Pure VMC unit."""
from __future__ import annotations

import asyncio
import logging
import re
from typing import Any

import aiohttp

from .const import (
    ENDPOINT_BOOST,
    ENDPOINT_SPEED,
    ENDPOINT_TEMP_EXHAUST,
    ENDPOINT_TEMP_EXTERNAL,
    ENDPOINT_TEMP_INLET,
    ENDPOINT_TEMP_RETURN,
    PAYLOAD_BOOST,
    PAYLOAD_ON_OFF,
    PAYLOAD_SPEED_DOWN_ONE,
    PAYLOAD_SPEED_DOWN_TEN,
    PAYLOAD_SPEED_UP_ONE,
    PAYLOAD_SPEED_UP_TEN,
    REGEX_TEMP_EXHAUST,
    REGEX_TEMP_EXTERNAL,
    REGEX_TEMP_INLET,
    REGEX_TEMP_RETURN,
    REGEX_SPEED,
    SPEED_OFF,
    SPEED_TIMER_MODE,
    SPEED_MAX,
    SPEED_MIN,
)

_LOGGER = logging.getLogger(__name__)

REQUEST_TIMEOUT = 10  # seconds


class PureApiError(Exception):
    """Raised when communication with the device fails."""


class PureApi:
    """Wraps all HTTP calls to the Pure local web interface."""

    def __init__(self, host: str, session: aiohttp.ClientSession) -> None:
        # Normalise: strip trailing slash, ensure no scheme duplication
        host = host.rstrip("/")
        if not host.startswith("http://") and not host.startswith("https://"):
            host = f"http://{host}"
        self._base = host
        self._session = session

    # ------------------------------------------------------------------
    # Low-level helpers
    # ------------------------------------------------------------------

    async def _get(self, endpoint: str) -> str:
        url = f"{self._base}{endpoint}"
        try:
            async with self._session.get(url, timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)) as resp:
                resp.raise_for_status()
                return await resp.text()
        except asyncio.TimeoutError as err:
            raise PureApiError(f"Timeout fetching {url}") from err
        except aiohttp.ClientError as err:
            raise PureApiError(f"HTTP error fetching {url}: {err}") from err

    async def _post(self, endpoint: str, payload: str) -> None:
        url = f"{self._base}{endpoint}"
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        try:
            async with self._session.post(
                url,
                data=payload,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT),
            ) as resp:
                resp.raise_for_status()
        except asyncio.TimeoutError as err:
            raise PureApiError(f"Timeout posting to {url}") from err
        except aiohttp.ClientError as err:
            raise PureApiError(f"HTTP error posting to {url}: {err}") from err

    @staticmethod
    def _parse_float(html: str, pattern: str) -> float | None:
        match = re.search(pattern, html, re.DOTALL)
        if match:
            try:
                return float(match.group(1))
            except ValueError:
                return None
        return None

    # ------------------------------------------------------------------
    # Data fetchers
    # ------------------------------------------------------------------

    async def get_speed(self) -> dict[str, Any]:
        """
        Return a dict with:
          - speed (int): 0 (off), 10-100 (normal), 101 (Orologio/timer mode)
          - timer_mode (bool): True when the device is running its internal schedule
        """
        html = await self._get(ENDPOINT_SPEED)
        match = re.search(REGEX_SPEED, html, re.IGNORECASE)

        if not match:
            _LOGGER.warning("Unexpected speed HTML response: %s", html[:200])
            raise PureApiError("Could not parse speed from device response")

        raw = match.group(1).strip()

        if raw.lower() == "off":
            return {"speed": SPEED_OFF, "timer_mode": False}

        if raw.lower() == "orologio":
            return {"speed": SPEED_TIMER_MODE, "timer_mode": True}

        try:
            speed = int(raw.replace("%", ""))
            return {"speed": speed, "timer_mode": False}
        except ValueError:
            raise PureApiError(f"Unexpected speed value: {raw!r}")

    async def get_temp_external(self) -> float | None:
        """External (outdoor) air temperature — Te."""
        html = await self._get(ENDPOINT_TEMP_EXTERNAL)
        return self._parse_float(html, REGEX_TEMP_EXTERNAL)

    async def get_temp_return(self) -> float | None:
        """Return (indoor extract) air temperature — Tr."""
        html = await self._get(ENDPOINT_TEMP_RETURN)
        return self._parse_float(html, REGEX_TEMP_RETURN)

    async def get_temp_exhaust(self) -> float | None:
        """Exhaust air temperature after heat exchanger — Tx."""
        html = await self._get(ENDPOINT_TEMP_EXHAUST)
        return self._parse_float(html, REGEX_TEMP_EXHAUST)

    async def get_temp_inlet(self) -> float | None:
        """Supply (inlet) air temperature delivered into the building — Ti."""
        html = await self._get(ENDPOINT_TEMP_INLET)
        return self._parse_float(html, REGEX_TEMP_INLET)

    async def get_all(self) -> dict[str, Any]:
        """Fetch all values concurrently. Used by the coordinator."""
        results = await asyncio.gather(
            self.get_speed(),
            self.get_temp_external(),
            self.get_temp_return(),
            self.get_temp_exhaust(),
            self.get_temp_inlet(),
            return_exceptions=True,
        )

        speed_data, t_ext, t_ret, t_exh, t_in = results

        # If the speed call itself failed, propagate — it's the most critical value
        if isinstance(speed_data, Exception):
            raise PureApiError("Failed to fetch speed") from speed_data

        return {
            "speed": speed_data["speed"],
            "timer_mode": speed_data["timer_mode"],
            "temp_external": t_ext if not isinstance(t_ext, Exception) else None,
            "temp_return": t_ret if not isinstance(t_ret, Exception) else None,
            "temp_exhaust": t_exh if not isinstance(t_exh, Exception) else None,
            "temp_inlet": t_in if not isinstance(t_in, Exception) else None,
        }

    # ------------------------------------------------------------------
    # Commands
    # ------------------------------------------------------------------

    async def turn_on_off(self) -> None:
        await self._post("/ifspeed_sp.html", PAYLOAD_ON_OFF)

    async def boost(self) -> None:
        await self._post(ENDPOINT_BOOST, PAYLOAD_BOOST)

    async def speed_up_ten(self) -> None:
        await self._post("/ifspeed_sp.html", PAYLOAD_SPEED_UP_TEN)

    async def speed_down_ten(self) -> None:
        await self._post("/ifspeed_sp.html", PAYLOAD_SPEED_DOWN_TEN)

    async def speed_up_one(self) -> None:
        await self._post("/ifspeed_sp.html", PAYLOAD_SPEED_UP_ONE)

    async def speed_down_one(self) -> None:
        await self._post("/ifspeed_sp.html", PAYLOAD_SPEED_DOWN_ONE)

    async def set_speed(self, target: int, current: int) -> None:
        """
        Drive the device from `current` to `target` speed.

        Device constraints:
          - Valid running speeds: 20–100 (steps of 1 or 10)
          - Speeds 1–19 are NOT valid: the device goes to Off below 20
          - From Off, any +1 or +10 command restores the device's internally
            memorised last speed (ignoring the step magnitude).
            Strategy: send exactly ONE +1 to wake up, re-read the real speed,
            then adjust from there to the true target.

        Special cases:
          - target == 0   → explicit turn off via toggle
          - target == 101 → not settable; callers should use boost()
          - current == 101 (Orologio) → unknown speed; turn off first, then ramp up
        """
        if target == SPEED_TIMER_MODE:
            _LOGGER.warning("Cannot set speed to 101 (Orologio) directly. Use boost() instead.")
            return

        # Clamp target to valid range
        if target != SPEED_OFF:
            target = max(SPEED_MIN, min(SPEED_MAX, target))

        # Exit Orologio mode: turn off first, then proceed normally
        if current == SPEED_TIMER_MODE:
            await self.turn_on_off()
            await asyncio.sleep(1)
            current = SPEED_OFF

        # --- Turn off ---
        if target == SPEED_OFF:
            if current != SPEED_OFF:
                await self.turn_on_off()
            return

        # --- Wake from Off ---
        # Send exactly one +1 to trigger the device's internal restore,
        # then re-read the actual speed before deciding how to adjust.
        if current == SPEED_OFF:
            await self.speed_up_one()
            await asyncio.sleep(1)
            try:
                data = await self.get_speed()
                current = data["speed"]
                if current == SPEED_OFF:
                    # Device didn't wake — try once more with +10
                    await self.speed_up_ten()
                    await asyncio.sleep(1)
                    data = await self.get_speed()
                    current = data["speed"]
            except PureApiError:
                current = SPEED_MIN  # safe fallback

        if current == target:
            return

        # --- Ramp up ---
        if target > current:
            diff = target - current
            for _ in range(diff // 10):
                await self.speed_up_ten()
            for _ in range(diff % 10):
                await self.speed_up_one()
            return

        # --- Ramp down ---
        # Never send a step that would push speed below SPEED_MIN (20),
        # because the device turns off below that threshold.
        # Only turn_on_off() is allowed to reach 0.
        simulated = current
        while simulated - 10 >= target:
            await self.speed_down_ten()
            simulated -= 10
        while simulated > target and simulated > SPEED_MIN:
            await self.speed_down_one()
            simulated -= 1

    async def test_connection(self) -> bool:
        """Try a single GET to verify reachability. Used during config flow."""
        try:
            await self._get(ENDPOINT_SPEED)
            return True
        except PureApiError:
            return False
