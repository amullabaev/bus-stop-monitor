import re
import time

import pytest

from app.departures import PAST_GRACE_MINUTES, _build_platforms_for_feed
from app.gtfs_static import GtfsStatic, RouteMeta, TripMeta
from app.gtfs_realtime import StopPrediction

TIME_FORMAT = re.compile(r"^\d{2}:\d{2}$")


@pytest.fixture(autouse=True)
def _no_schedule(monkeypatch):
    monkeypatch.setattr(
        "app.departures._scheduled_predictions", lambda *args: [])


def test_build_platforms_groups_and_sorts_arrivals(monkeypatch):
    now = time.time()

    static_data = GtfsStatic(
        transport_type="bus",
        stops={"10000": "Głowackiego"},
        routes={"704": RouteMeta(route_short_name="704")},
        trips={
            "tripA": TripMeta(route_id="704", trip_headsign="Bronowice Małe"),
            "tripB": TripMeta(route_id="704", trip_headsign="Bronowice Małe"),
        },
    )
    monkeypatch.setattr("app.departures.get_static_data",
                        lambda feed_key: static_data)

    predictions = [
        StopPrediction(trip_id="tripB", route_id="704",
                       stop_id="10000", eta_epoch=int(now + 600)),
        StopPrediction(trip_id="tripA", route_id="704",
                       stop_id="10000", eta_epoch=int(now + 120)),
        # far in the past -> should be dropped
        StopPrediction(trip_id="tripA", route_id="704",
                       stop_id="10000", eta_epoch=int(now - 600)),
    ]
    monkeypatch.setattr(
        "app.departures.get_stop_predictions", lambda feed_key, stop_ids: predictions
    )

    platforms = _build_platforms_for_feed("bus")

    assert len(platforms) == 1
    platform = platforms[0]
    assert platform.stop_id == "10000"
    assert len(platform.lines) == 1
    line = platform.lines[0]
    assert line.route_short_name == "704"
    assert line.headsign == "Bronowice Małe"
    assert [arrival.minutes for arrival in line.arrivals] == [2, 10]
    assert all(TIME_FORMAT.match(arrival.time) for arrival in line.arrivals)


def test_past_grace_allows_just_departed_bus(monkeypatch):
    now = time.time()
    static_data = GtfsStatic(
        transport_type="bus",
        stops={"10000": "Głowackiego"},
        routes={"704": RouteMeta(route_short_name="704")},
        trips={"tripA": TripMeta(
            route_id="704", trip_headsign="Bronowice Małe")},
    )
    monkeypatch.setattr("app.departures.get_static_data",
                        lambda feed_key: static_data)

    predictions = [
        StopPrediction(
            trip_id="tripA",
            route_id="704",
            stop_id="10000",
            eta_epoch=int(now - (PAST_GRACE_MINUTES * 60 - 5)),
        )
    ]
    monkeypatch.setattr(
        "app.departures.get_stop_predictions", lambda feed_key, stop_ids: predictions
    )

    platforms = _build_platforms_for_feed("bus")
    assert len(platforms) == 1
    assert [arrival.minutes for arrival in platforms[0].lines[0].arrivals] == [-1]
