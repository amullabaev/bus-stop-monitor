from app.stops import normalize, find_matching_stops
from app.gtfs_static import GtfsStatic


def test_normalize_strips_polish_diacritics():
    assert normalize("Głowackiego") == "glowackiego"
    assert normalize("Glowackiego") == "glowackiego"
    assert normalize("Wąchock-Śródmieście") == "wachocksrodmiescie"


def test_find_matching_stops_matches_both_spellings():
    data = GtfsStatic(
        transport_type="bus",
        stops={
            "1": "Głowackiego",
            "2": "Glowackiego (SKA)",
            "3": "Rondo Mogilskie",
        },
    )
    matches = find_matching_stops(data, "glowackiego")
    assert matches == {"1": "Głowackiego", "2": "Glowackiego (SKA)"}
