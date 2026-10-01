# bus-stop-monitor

Minimalistic live departure board for a bus stop in Kraków, built on ZTP Kraków's public GTFS + GTFS-Realtime feeds.

## Run

```powershell
python -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt
.\.venv\Scripts\python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Open http://127.0.0.1:8000/ on this machine, or http://<this-machine-LAN-IP>:8000/ from your phone (same Wi-Fi network; check the machine's LAN IP with `ipconfig`, and allow the port through the firewall if prompted).

## Tests

```powershell
.\.venv\Scripts\python -m pytest
```

## Notes

- Data source: https://gtfs.ztp.krakow.pl/ (GTFS static zips + GTFS-Realtime TripUpdates protobufs), no API key required.
- `data/` holds a cached copy of the GTFS static zips (auto-refreshed after 24h).


## Plans

- Save a list of frequently used stops for quicker access.
- Using location services, suggesting nearby stops automatically.