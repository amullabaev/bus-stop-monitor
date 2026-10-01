"""Download, cache and parse the GTFS static feeds (stops/routes/trips)."""
from __future__ import annotations

import csv
import io
import time
import zipfile
from dataclasses import dataclass, field
from datetime import date

import requests

from . import config


@dataclass
class RouteMeta:
    route_short_name: str


@dataclass
class TripMeta:
    route_id: str
    trip_headsign: str
    service_id: str = ""


@dataclass
class StopMeta:
    code: str = ""  # e.g. "100-03"
    pole: str = ""  # stop_desc, the numbered pole at the stop
    lat: float | None = None
    lon: float | None = None
    wheelchair: bool = False


@dataclass
class GtfsStatic:
    transport_type: str  # "bus" | "tram"
    stops: dict[str, str] = field(default_factory=dict)  # stop_id -> stop_name
    stop_meta: dict[str, StopMeta] = field(default_factory=dict)
    routes: dict[str, RouteMeta] = field(
        default_factory=dict)  # route_id -> RouteMeta
    trips: dict[str, TripMeta] = field(
        default_factory=dict)  # trip_id -> TripMeta
    # service_id -> (weekday flags mon..sun, start, end) with dates as ISO-comparable ints
    calendar: dict[str, tuple[tuple[bool, ...], int, int]] = field(
        default_factory=dict)
    # (service_id, yyyymmdd) -> True if added, False if removed
    calendar_exceptions: dict[tuple[str, int], bool] = field(
        default_factory=dict)

    def service_active(self, service_id: str, day: date) -> bool:
        key = day.year * 10000 + day.month * 100 + day.day
        exception = self.calendar_exceptions.get((service_id, key))
        if exception is not None:
            return exception
        entry = self.calendar.get(service_id)
        if not entry:
            return False
        weekdays, start, end = entry
        return start <= key <= end and weekdays[day.weekday()]


def _zip_path(feed_key: str) -> "config.Path":
    filename = config.FEEDS[feed_key]["static"]
    return config.DATA_DIR / filename


def ensure_static_zip(feed_key: str) -> "config.Path":
    """Download the GTFS static zip for feed_key if missing or stale, return its path."""
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    path = _zip_path(feed_key)
    if path.exists() and (time.time() - path.stat().st_mtime) < config.STATIC_CACHE_MAX_AGE_SECONDS:
        return path

    url = f"{config.GTFS_BASE_URL}/{config.FEEDS[feed_key]['static']}"
    response = requests.get(url, timeout=config.HTTP_TIMEOUT_SECONDS)
    response.raise_for_status()
    path.write_bytes(response.content)
    return path


def _read_csv(zf: zipfile.ZipFile, filename: str):
    with zf.open(filename) as raw:
        text = io.TextIOWrapper(raw, encoding="utf-8-sig")
        yield from csv.DictReader(text)


def load_static_data(feed_key: str) -> GtfsStatic:
    """Parse stops/routes/trips out of the cached GTFS static zip for feed_key."""
    path = ensure_static_zip(feed_key)
    data = GtfsStatic(transport_type=feed_key)
    _schedule_cache.clear()

    with zipfile.ZipFile(path) as zf:
        for row in _read_csv(zf, "stops.txt"):
            data.stops[row["stop_id"]] = row["stop_name"]
            data.stop_meta[row["stop_id"]] = StopMeta(
                code=row.get("stop_code", ""),
                pole=row.get("stop_desc", ""),
                lat=float(row["stop_lat"]) if row.get("stop_lat") else None,
                lon=float(row["stop_lon"]) if row.get("stop_lon") else None,
                wheelchair=row.get("wheelchair_boarding") == "1",
            )

        for row in _read_csv(zf, "routes.txt"):
            data.routes[row["route_id"]] = RouteMeta(
                route_short_name=row["route_short_name"])

        for row in _read_csv(zf, "trips.txt"):
            data.trips[row["trip_id"]] = TripMeta(
                route_id=row["route_id"],
                trip_headsign=row.get("trip_headsign", ""),
                service_id=row.get("service_id", ""),
            )

        for row in _read_csv(zf, "calendar.txt"):
            weekdays = tuple(row[d] == "1" for d in (
                "monday", "tuesday", "wednesday", "thursday",
                "friday", "saturday", "sunday"))
            data.calendar[row["service_id"]] = (
                weekdays, int(row["start_date"]), int(row["end_date"]))

        for row in _read_csv(zf, "calendar_dates.txt"):
            data.calendar_exceptions[(row["service_id"], int(row["date"]))] = (
                row["exception_type"] == "1")

    return data


_schedule_cache: dict[tuple[str, frozenset[str]],
                      list[tuple[str, str, int]]] = {}


def load_stop_schedule(feed_key: str, stop_ids: frozenset[str]) -> list[tuple[str, str, int]]:
    """Return (trip_id, stop_id, departure seconds after service-day midnight) for stop_ids."""
    key = (feed_key, stop_ids)
    if key in _schedule_cache:
        return _schedule_cache[key]

    rows: list[tuple[str, str, int]] = []
    with zipfile.ZipFile(ensure_static_zip(feed_key)) as zf:
        for row in _read_csv(zf, "stop_times.txt"):
            if row["stop_id"] not in stop_ids:
                continue
            hours, minutes, seconds = row["departure_time"].split(":")
            rows.append((row["trip_id"], row["stop_id"],
                         int(hours) * 3600 + int(minutes) * 60 + int(seconds)))
    _schedule_cache[key] = rows
    return rows
