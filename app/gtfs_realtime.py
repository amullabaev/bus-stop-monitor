"""Fetch and parse GTFS-Realtime TripUpdates feeds."""
from __future__ import annotations

import time
from dataclasses import dataclass

import requests
from google.protobuf.message import DecodeError
from google.transit import gtfs_realtime_pb2

from . import config

_cache: dict[str, tuple[float, gtfs_realtime_pb2.FeedMessage]] = {}
FETCH_ATTEMPTS = 3


@dataclass
class StopPrediction:
    trip_id: str
    route_id: str
    stop_id: str
    eta_epoch: int


def _fetch_feed(feed_key: str) -> gtfs_realtime_pb2.FeedMessage:
    """Download and parse TripUpdates for feed_key; only valid feeds are cached."""
    cached = _cache.get(feed_key)
    now = time.time()
    if cached and (now - cached[0]) < config.REALTIME_CACHE_MAX_AGE_SECONDS:
        return cached[1]

    url = f"{config.GTFS_BASE_URL}/{config.FEEDS[feed_key]['trip_updates']}"
    last_error: Exception | None = None
    for _ in range(FETCH_ATTEMPTS):
        try:
            response = requests.get(url, timeout=config.HTTP_TIMEOUT_SECONDS)
            response.raise_for_status()
            feed = gtfs_realtime_pb2.FeedMessage()
            feed.ParseFromString(response.content)
        except (requests.RequestException, DecodeError) as err:
            last_error = err
            continue
        _cache[feed_key] = (now, feed)
        return feed

    # the server sometimes serves truncated data; reuse the last good feed if we have one
    if cached:
        return cached[1]
    raise last_error  # type: ignore[misc]


def get_realtime_trip_ids(feed_key: str) -> set[str]:
    """Trip ids that have any TripUpdate in the feed (their timing comes from realtime)."""
    return {
        entity.trip_update.trip.trip_id
        for entity in _fetch_feed(feed_key).entity
        if entity.HasField("trip_update")
    }


def get_stop_predictions(feed_key: str, stop_ids: set[str]) -> list[StopPrediction]:
    """Return every StopTimeUpdate for the given stop_ids from the feed's TripUpdates."""
    feed = _fetch_feed(feed_key)

    predictions: list[StopPrediction] = []
    for entity in feed.entity:
        if not entity.HasField("trip_update"):
            continue
        trip_update = entity.trip_update
        for stop_time_update in trip_update.stop_time_update:
            if stop_time_update.stop_id not in stop_ids:
                continue
            # arrival time is unset (0) for a trip's first stop; fall back to departure time
            eta_epoch = stop_time_update.arrival.time or stop_time_update.departure.time
            if not eta_epoch:
                continue
            predictions.append(
                StopPrediction(
                    trip_id=trip_update.trip.trip_id,
                    route_id=trip_update.trip.route_id,
                    stop_id=stop_time_update.stop_id,
                    eta_epoch=eta_epoch,
                )
            )
    return predictions
