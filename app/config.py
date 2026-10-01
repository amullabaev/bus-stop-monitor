"""Central configuration constants for the departure board."""
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

GTFS_BASE_URL = "https://gtfs.ztp.krakow.pl"

TIMEZONE = "Europe/Warsaw"

# feed key -> (static zip filename, realtime trip updates filename, transport type label)
FEEDS = {
    "bus": {"static": "GTFS_KRK_A.zip", "trip_updates": "TripUpdates_A.pb"},
    "tram": {"static": "GTFS_KRK_T.zip", "trip_updates": "TripUpdates_T.pb"},
}

# normalized (diacritics stripped, lowercase) match
TARGET_STOP_QUERY = "glowackiego"

STATIC_CACHE_MAX_AGE_SECONDS = 24 * 60 * 60
REALTIME_CACHE_MAX_AGE_SECONDS = 15
ARRIVALS_PER_GROUP = 4

HTTP_TIMEOUT_SECONDS = 10
