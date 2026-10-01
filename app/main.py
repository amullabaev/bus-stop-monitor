"""FastAPI app: serves the departures API and the static frontend."""
from __future__ import annotations

import requests
from fastapi import FastAPI, HTTPException, Query
from fastapi.staticfiles import StaticFiles
from google.protobuf.message import DecodeError
from pathlib import Path

from .departures import build_departures_view, reload_static_data, search_stops

app = FastAPI(title="Public transport departure board")

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


@app.on_event("startup")
def on_startup() -> None:
    reload_static_data()


@app.get("/api/stops")
def get_stops(q: str = Query("", max_length=100)) -> list[str]:
    return search_stops(q)


@app.get("/api/departures")
def get_departures(stop: str | None = Query(None, max_length=100)) -> dict:
    try:
        return build_departures_view(stop)
    except (requests.RequestException, DecodeError) as err:
        raise HTTPException(
            status_code=503, detail="Realtime feed unavailable") from err


app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
