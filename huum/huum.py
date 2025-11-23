from typing import Any, Optional
from urllib.parse import urljoin

import aiohttp
from aiohttp import ClientResponse

from huum.schemas import HuumStatusResponse

API_BASE = "https://sauna.huum.eu/action/"
API_HOME_BASE = f"{API_BASE}home/"

class Huum:
    min_temp = 40
    max_temp = 110
    session: aiohttp.ClientSession

    def __init__(self, username: str, password: str, session: Optional[aiohttp.ClientSession] = None) -> None:
        if session:
            self.session = session
        self.auth = aiohttp.BasicAuth(username, password)

    async def _make_call(self, method: str, url: str, json: Any | None = None) -> ClientResponse:
        call_args = {
            "url": url,
            "auth": self.auth,
        }
        if json:
            call_args["json"] = json
        call_request = getattr(self.session, method.lower())
        response: ClientResponse = await call_request(**call_args)
        response.raise_for_status()
        return response

    async def open_session(self) -> None:
        self.session = aiohttp.ClientSession()

    async def close_session(self) -> None:
        await self.session.close()

    async def status(self) -> HuumStatusResponse:
        url = urljoin(API_HOME_BASE, "status")
        response = await self._make_call("get", url)
        data = await response.json()
        return HuumStatusResponse.from_dict(data)

    async def turn_on(self, temperature: int) -> HuumStatusResponse:
        if temperature < self.min_temp or temperature > self.max_temp:
            raise ValueError("Lämpötila pitää olla 40–110 °C")
        url = urljoin(API_HOME_BASE, "start")
        data = {"targetTemperature": temperature}
        response = await self._make_call("post", url, json=data)
        return HuumStatusResponse.from_dict(await response.json())

    async def turn_off(self) -> HuumStatusResponse:
        url = urljoin(API_HOME_BASE, "stop")
        response = await self._make_call("post", url)
        return HuumStatusResponse.from_dict(await response.json())

    async def toggle_light(self) -> HuumStatusResponse:
        url = urljoin(API_HOME_BASE, "light")
        response = await self._make_call("get", url)
        return HuumStatusResponse.from_dict(await response.json())
