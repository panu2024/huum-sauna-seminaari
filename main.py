import os
import sys
import json
import asyncio
import datetime
import traceback
import logging

from aiohttp import web, ClientSession, ClientTimeout
from icalendar import Calendar
from huum.huum import Huum


logging.basicConfig(stream=sys.stdout, level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger("sauna")

def log_exc(msg: str, e: Exception):
    log.error("%s: %r\n%s", msg, e, traceback.format_exc())


KÄYTTÄJÄTUNNUS = "**********"
SALASANA = "***********"

TAVOITE_LAMPOTILA = 92
KESTO_SEKUNTEINA = 60 * 60
ICAL_URL = "http://www.saunaonline.fi/publicmodules/ical/880/cf6ffd71132f890947455833b9288608"

ICAL_TIMEOUT = ClientTimeout(total=15, connect=5)

routes = web.RouteTableDef()


@routes.get("/")
async def index(request):
    return web.FileResponse(path="static/index.html")

@routes.get("/healthz")
async def healthz(request):
    return web.Response(text="ok")


async def with_huum_session(fn):

    huum = Huum(username=KÄYTTÄJÄTUNNUS, password=SALASANA)
    try:
        await huum.open_session()
    except Exception as e:
        log_exc("HUUM open_session failed", e)
        return None, f"HUUM open_session failed: {e}", 503
    try:
        data = await fn(huum)
        return data, None, 200
    except Exception as e:
        log_exc("HUUM call failed", e)
        return None, str(e), 503
    finally:
        try:
            await huum.close_session()
        except Exception as e:
            log_exc("HUUM close_session failed", e)


@routes.post("/start")
async def start_sauna(request):
    data = await request.post()
    try:
        target_temp = int(data.get("temperature", TAVOITE_LAMPOTILA))
    except Exception:
        target_temp = TAVOITE_LAMPOTILA

    async def _do(huum):
        return await huum.turn_on(temperature=target_temp)

    res, err, code = await with_huum_session(_do)
    if err:
        return web.Response(status=code, text=f"Virhe käynnistyksessä: {err}")
    log.info("HUUM turn_on ok: %s", str(res)[:200])
    return web.Response(text=f"🔥 Sauna käynnistetty: {res}")

@routes.post("/stop")
async def stop_sauna(request):
    async def _do(huum):
        return await huum.turn_off()

    res, err, code = await with_huum_session(_do)
    if err:
        return web.Response(status=code, text=f"Virhe sammutuksessa: {err}")
    log.info("HUUM turn_off ok: %s", str(res)[:200])
    return web.Response(text=f"🢨 Sauna sammutettu: {res}")

@routes.get("/status")
async def sauna_status(request):
    async def _do(huum):
        return await huum.status()

    status, err, code = await with_huum_session(_do)

    
    automaattinen = False
    timestamp = None
    try:
        if os.path.exists("tila.json"):
            with open("tila.json", "r") as f:
                data = json.load(f)
                automaattinen = bool(data.get("automaattinen", False))
                timestamp = data.get("timestamp")
    except Exception as e:
        log_exc("tila.json read failed", e)

    if status is None:
        
        return web.json_response({
            "temperature": None,
            "is_on": False,
            "status_code": None,
            "automaattinen": automaattinen,
            "timestamp": timestamp,
            "error": err or "HUUM status unavailable"
        }, status=code)

    temperature = getattr(status, "temperature", None)
    status_code = getattr(status, "status", None)
    is_on = (status_code == 3)

    return web.json_response({
        "temperature": temperature,
        "is_on": is_on,
        "status_code": status_code,
        "automaattinen": automaattinen,
        "timestamp": timestamp
    })


@routes.get("/reservations")
async def hae_varaukset(request):
    try:
        async with ClientSession(timeout=ICAL_TIMEOUT) as session:
            async with session.get(ICAL_URL) as response:
                if response.status >= 400:
                    txt = await response.text()
                    log.error("ICAL HTTP %s: %s", response.status, txt[:400])
                    return web.json_response({"error": f"iCal HTTP {response.status}"}, status=502)
                ical_data = await response.read()

        cal = Calendar.from_ical(ical_data)
        nyt = datetime.datetime.now(datetime.timezone.utc)
        viikon_paasta = nyt + datetime.timedelta(days=7)

        tapahtumat = []
        for component in cal.walk():
            if component.name == "VEVENT":
                alku = component.get("dtstart").dt
                otsikko = str(component.get("summary"))
                if isinstance(alku, datetime.datetime):
                    
                    if alku.tzinfo is None:
                        alku = alku.replace(tzinfo=datetime.timezone.utc)
                    else:
                        alku = alku.astimezone(datetime.timezone.utc)
                    if nyt <= alku <= viikon_paasta:
                        tapahtumat.append({
                            "aika": alku.isoformat(),
                            "otsikko": otsikko
                        })

        return web.json_response(tapahtumat)

    except Exception as e:
        log_exc("reservations failed", e)
        return web.json_response({"error": str(e)}, status=500)


app = web.Application()
app.add_routes(routes)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    web.run_app(app, host="0.0.0.0", port=port)

