import aiohttp
import asyncio
import datetime
import json
import os
import sys
from icalendar import Calendar
from aiohttp import ClientTimeout

# 🔧 Tulostus näkyviin heti lokeihin
try:
    sys.stdout.reconfigure(line_buffering=True)
except Exception:
    pass

# -----------------------------
# Konfiguraatio (env -> voi yliajaa)
# -----------------------------
SERVICE_URL = os.getenv("SERVICE_URL", "https://sauna-ohjain-app-404868803234.europe-north1.run.app")
START_URL = f"{SERVICE_URL}/start"
STOP_URL = f"{SERVICE_URL}/stop"

ICAL_URL = os.getenv("ICAL_URL", "http://www.saunaonline.fi/publicmodules/ical/880/cf6ffd71132f890947455833b9288608")
TILA_POLKU = os.getenv("STATE_FILE", "tila.json")

# Aikaikkunat
EARLY_START_MIN = int(os.getenv("EARLY_START_MIN", "65"))  # käynnistä 1–65 min ennen alkua
MIN_LEAD_MIN = int(os.getenv("MIN_LEAD_MIN", "1"))        # ei liian aikaisin
GAP_KEEP_ON_MIN = int(os.getenv("GAP_KEEP_ON_MIN", "65")) # jos seuraava alkaa < 65 min edellisen lopusta -> jätä päälle

# Timeoutit
HTTP_TIMEOUT = ClientTimeout(total=15, connect=5)
ICAL_TIMEOUT = ClientTimeout(total=15, connect=5)

# -----------------------------
# iCal apurit
# -----------------------------
async def hae_ical():
    async with aiohttp.ClientSession(timeout=ICAL_TIMEOUT) as session:
        async with session.get(ICAL_URL) as resp:
            if resp.status >= 400:
                text = await resp.text()
                raise RuntimeError(f"iCal HTTP {resp.status}: {text[:300]}")
            return await resp.read()

def _to_utc(dt):
    # dt voi olla date tai datetime, normalisoidaan UTC:hen
    if isinstance(dt, datetime.date) and not isinstance(dt, datetime.datetime):
        # All-day tapahtuma -> oletetaan klo 00:00 UTC
        dt = datetime.datetime(dt.year, dt.month, dt.day, tzinfo=datetime.timezone.utc)
        return dt
    if isinstance(dt, datetime.datetime):
        if dt.tzinfo is None:
            return dt.replace(tzinfo=datetime.timezone.utc)
        return dt.astimezone(datetime.timezone.utc)
    return None

def pura_tapahtumat(ical_data):
    tapahtumat = []
    cal = Calendar.from_ical(ical_data)
    for component in cal.walk():
        if component.name == "VEVENT":
            alku = _to_utc(component.get("dtstart").dt)
            loppu = _to_utc(component.get("dtend").dt)
            otsikko = str(component.get("summary"))
            if alku and loppu:
                tapahtumat.append({"alku": alku, "loppu": loppu, "otsikko": otsikko})
    return tapahtumat

# -----------------------------
# HTTP apurit (pieni retry)
# -----------------------------
async def _post_with_retry(url, payload=None, tries=2):
    last_err = None
    for attempt in range(1, tries + 1):
        try:
            async with aiohttp.ClientSession(timeout=HTTP_TIMEOUT) as session:
                async with session.post(url, data=payload or {}) as resp:
                    text = await resp.text()
                    if resp.status >= 400:
                        raise RuntimeError(f"POST {url} -> HTTP {resp.status}: {text[:300]}")
                    return text
        except Exception as e:
            last_err = e
            if attempt < tries:
                await asyncio.sleep(1.5 * attempt)  # kevyt backoff
    raise last_err

# -----------------------------
# Päätöslogiikka
# -----------------------------
async def tarkista_lammitys_tarve():
    print("🔎 Sauna checker käynnistyi", flush=True)

    nyt = datetime.datetime.now(datetime.timezone.utc)
    aika_min = nyt + datetime.timedelta(minutes=MIN_LEAD_MIN)
    aika_max = nyt + datetime.timedelta(minutes=EARLY_START_MIN)

    # 1) iCal
    try:
        ical_data = await hae_ical()
        tapahtumat = pura_tapahtumat(ical_data)
        print(f"📓 Kalenterista haettu {len(tapahtumat)} tapahtumaa", flush=True)
    except Exception as e:
        print("❌ Virhe kalenterin hakemisessa:", e, flush=True)
        return

    tapahtumat = sorted(tapahtumat, key=lambda t: t["alku"])

    # Etsi “relevantti” tapahtuma: jonka loppu on > nyt-5min (eli on käynnissä tai tulossa)
    seuraava = next(
        (t for t in tapahtumat if t["loppu"] > nyt - datetime.timedelta(minutes=5)),
        None
    )

    kaynnistettiin = False
    sammutettiin = False

    if seuraava:
        alku = seuraava["alku"]
        loppu = seuraava["loppu"]
        otsikko = seuraava["otsikko"]
        print(f"▶️ Valittu vuoro: alku={alku.isoformat()}, loppu={loppu.isoformat()}, nyt={nyt.isoformat()}", flush=True)

        if nyt < alku:
            # Vuoro tulevaisuudessa -> käynnistä 1–EARLY_START_MIN min ennen
            if aika_min <= alku <= aika_max:
                print(f"✅ Käynnistetään sauna, vuoro alkaa {alku.isoformat()} otsikolla '{otsikko}'", flush=True)
                try:
                    vastaus = await _post_with_retry(START_URL)
                    print("🔥 Start-komento OK:", vastaus[:200], flush=True)
                    _kirjoita_tila_json(automaattinen=True)
                    kaynnistettiin = True
                except Exception as e:
                    print("❌ Virhe saunan käynnistyksessä:", e, flush=True)
            else:
                print("⏳ Ei vielä käynnistetä (ei aikahaarukassa)", flush=True)

        elif alku <= nyt <= loppu:
            print(f"♨️ Vuoro käynnissä ({alku.isoformat()}–{loppu.isoformat()}) – ei tehdä mitään", flush=True)

        else:  # nyt > loppu
            # Tarkista alkaako seuraava pian; jos ei, sammuta
            seuraavat = [t for t in tapahtumat if t["alku"] > loppu]
            if seuraavat and (seuraavat[0]["alku"] - loppu) < datetime.timedelta(minutes=GAP_KEEP_ON_MIN):
                print("🕒 Uusi vuoro pian – ei sammuteta", flush=True)
            else:
                print("🛑 Sammutetaan sauna, vuoro päättynyt", flush=True)
                try:
                    vastaus = await _post_with_retry(STOP_URL)
                    print("🧊 Stop-komento OK:", vastaus[:200], flush=True)
                    _poista_tila_json()
                    sammutettiin = True
                except Exception as e:
                    print("❌ Virhe saunan sammutuksessa:", e, flush=True)

    # Ei tehty mitään -> siivoa tila.json maltilla
    if not kaynnistettiin and not sammutettiin:
        _poista_tila_json(silent=True)
        print("👶 Ei varauksia lähihorisontissa – tila.json siivottu tarvittaessa", flush=True)

def _kirjoita_tila_json(automaattinen: bool):
    try:
        with open(TILA_POLKU, "w") as f:
            json.dump(
                {"automaattinen": bool(automaattinen), "timestamp": datetime.datetime.utcnow().isoformat() + "Z"},
                f
            )
    except Exception as e:
        print("⚠️ tila.json kirjoitus epäonnistui:", e, flush=True)

def _poista_tila_json(silent=False):
    try:
        if os.path.exists(TILA_POLKU):
            os.remove(TILA_POLKU)
            if not silent:
                print("🧽 Poistettu tila.json", flush=True)
    except Exception as e:
        print("⚠️ tila.json poisto epäonnistui:", e, flush=True)

# 🔁 Cloud Run Job: suorita ja poistu
if __name__ == "__main__":
    asyncio.run(tarkista_lammitys_tarve())
