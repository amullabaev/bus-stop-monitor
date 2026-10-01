"""Combine GTFS static + realtime data into the JSON view model served to the frontend."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from . import config
from .gtfs_realtime import StopPrediction, get_realtime_trip_ids, get_stop_predictions
from .gtfs_static import GtfsStatic, StopMeta, load_static_data, load_stop_schedule
from .stops import find_matching_stops, search_stop_names

# a departure that's this far in the past is still shown (bus may be at the stop / boarding)
PAST_GRACE_MINUTES = 1

# timetable-only departures (no realtime data yet) are shown this far ahead
SCHEDULE_HORIZON_MINUTES = 60

# max flat upcoming departures kept per platform (for the LED board)
UPCOMING_LIMIT = 6

_DISPLAY_TZ = ZoneInfo(config.TIMEZONE)


@dataclass
class Arrival:
    minutes: int
    time: str  # local HH:MM, e.g. "14:32"


@dataclass
class LineGroup:
    route_short_name: str
    headsign: str
    transport_type: str
    arrivals: list[Arrival] = field(default_factory=list)


def _format_local_time(epoch_seconds: int) -> str:
    return datetime.fromtimestamp(epoch_seconds, tz=_DISPLAY_TZ).strftime("%H:%M")


@dataclass
class Platform:
    stop_id: str
    stop_name: str
    lines: list[LineGroup] = field(default_factory=list)
    upcoming: list[dict] = field(default_factory=list)
    meta: StopMeta = field(default_factory=StopMeta)


_static_cache: dict[str, GtfsStatic] = {}


def get_static_data(feed_key: str) -> GtfsStatic:
    """Load (and memoize in-process) the GTFS static data for feed_key."""
    if feed_key not in _static_cache:
        _static_cache[feed_key] = load_static_data(feed_key)
    return _static_cache[feed_key]


def reload_static_data() -> None:
    """Force a fresh load of all feeds' static data (e.g. daily refresh)."""
    for feed_key in config.FEEDS:
        _static_cache[feed_key] = load_static_data(feed_key)


def _scheduled_predictions(
    feed_key: str, static_data: GtfsStatic, stop_ids: set[str], now: float
) -> list[StopPrediction]:
    """Timetable departures for trips absent from realtime (not started yet / no vehicle)."""
    realtime_trips = get_realtime_trip_ids(feed_key)
    schedule = load_stop_schedule(feed_key, frozenset(stop_ids))
    today = datetime.fromtimestamp(now, tz=_DISPLAY_TZ).date()
    lower = now - PAST_GRACE_MINUTES * 60
    upper = now + SCHEDULE_HORIZON_MINUTES * 60

    predictions: list[StopPrediction] = []
    # yesterday's service day covers after-midnight times like 24:15:00
    for day in (today - timedelta(days=1), today):
        midnight = datetime(day.year, day.month, day.day,
                            tzinfo=_DISPLAY_TZ).timestamp()
        for trip_id, stop_id, seconds in schedule:
            epoch = midnight + seconds
            if not lower <= epoch <= upper or trip_id in realtime_trips:
                continue
            trip = static_data.trips.get(trip_id)
            if not trip or not static_data.service_active(trip.service_id, day):
                continue
            predictions.append(StopPrediction(
                trip_id=trip_id, route_id=trip.route_id,
                stop_id=stop_id, eta_epoch=int(epoch)))
    return predictions


def search_stops(query: str) -> list[str]:
    return search_stop_names([get_static_data(k) for k in config.FEEDS], query)


def _build_platforms_for_feed(feed_key: str, stop_name: str | None = None) -> list[Platform]:
    static_data = get_static_data(feed_key)
    if stop_name is None:
        matching_stops = find_matching_stops(
            static_data, config.TARGET_STOP_QUERY)
    else:
        matching_stops = find_matching_stops(
            static_data, stop_name, exact=True)
    if not matching_stops:
        return []

    predictions = get_stop_predictions(feed_key, set(matching_stops))
    now = time.time()
    predictions = predictions + _scheduled_predictions(
        feed_key, static_data, set(matching_stops), now)

    # group predictions by (stop_id, route_short_name, headsign)
    groups: dict[tuple[str, str, str], list[tuple[int, int]]] = {}
    for prediction in predictions:
        eta_minutes = round((prediction.eta_epoch - now) / 60)
        if eta_minutes < -PAST_GRACE_MINUTES:
            continue
        trip = static_data.trips.get(prediction.trip_id)
        # realtime route_id can be wrong (block id prefix); static trip is authoritative
        route_id = trip.route_id if trip else prediction.route_id
        route = static_data.routes.get(route_id)
        route_short_name = route.route_short_name if route else route_id
        headsign = trip.trip_headsign if trip else ""
        key = (prediction.stop_id, route_short_name, headsign)
        groups.setdefault(key, []).append((eta_minutes, prediction.eta_epoch))

    platforms: dict[str, Platform] = {}
    for (stop_id, route_short_name, headsign), etas in groups.items():
        platform = platforms.setdefault(
            stop_id, Platform(
                stop_id=stop_id, stop_name=matching_stops[stop_id],
                meta=static_data.stop_meta.get(stop_id, StopMeta()))
        )
        etas.sort(key=lambda pair: pair[0])
        platform.upcoming.extend(
            {
                "route_short_name": route_short_name,
                "headsign": headsign,
                "minutes": minutes,
                "time": _format_local_time(epoch),
            }
            for minutes, epoch in etas[:UPCOMING_LIMIT]
        )
        arrivals = [
            Arrival(minutes=minutes, time=_format_local_time(epoch))
            for minutes, epoch in etas[: config.ARRIVALS_PER_GROUP]
        ]
        platform.lines.append(
            LineGroup(
                route_short_name=route_short_name,
                headsign=headsign,
                transport_type=feed_key,
                arrivals=arrivals,
            )
        )

    for platform in platforms.values():
        platform.lines.sort(key=lambda line: line.arrivals[0].minutes)
        platform.upcoming.sort(key=lambda item: item["minutes"])
        del platform.upcoming[UPCOMING_LIMIT:]

    return sorted(platforms.values(), key=lambda p: p.stop_id)


def build_departures_view(stop_name: str | None = None) -> dict:
    """Build the full JSON-serializable view model shown by the frontend."""
    platforms: list[Platform] = []
    for feed_key in config.FEEDS:
        platforms.extend(_build_platforms_for_feed(feed_key, stop_name))

    return {
        "generated_at": int(time.time()),
        "stop_name": stop_name or (platforms[0].stop_name if platforms else ""),
        "platforms": [
            {
                "stop_id": platform.stop_id,
                "stop_name": platform.stop_name,
                "code": platform.meta.code,
                "pole": platform.meta.pole,
                "lat": platform.meta.lat,
                "lon": platform.meta.lon,
                "wheelchair": platform.meta.wheelchair,
                # unique headsigns in soonest-first order, as a readable direction
                "directions": list(dict.fromkeys(
                    line.headsign for line in platform.lines if line.headsign)),
                "upcoming": platform.upcoming,
                "lines": [
                    {
                        "route_short_name": line.route_short_name,
                        "headsign": line.headsign,
                        "transport_type": line.transport_type,
                        "arrivals": [
                            {"minutes": arrival.minutes, "time": arrival.time}
                            for arrival in line.arrivals
                        ],
                    }
                    for line in platform.lines
                ],
            }
            for platform in platforms
        ],
    }
