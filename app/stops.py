"""Stop-name normalization and matching (handles Polish diacritics)."""
from __future__ import annotations

import unicodedata

from .gtfs_static import GtfsStatic

_POLISH_MAP = str.maketrans(
    "ąĄćĆęĘłŁńŃóÓśŚźŹżŻ",
    "aAcCeElLnNoOsSzZzZ",
)


def normalize(text: str) -> str:
    """Lowercase text with Polish diacritics stripped, keeping only alphanumerics."""
    translated = text.translate(_POLISH_MAP)
    # divide "complex" letters into simple ascii + additional, "ą" -> "a + \u0328"
    decomposed = unicodedata.normalize("NFKD", translated)
    ascii_only = "".join(
        ch for ch in decomposed if not unicodedata.combining(ch))
    return "".join(ch for ch in ascii_only.lower() if ch.isalnum())


def find_matching_stops(data: GtfsStatic, query: str, exact: bool = False) -> dict[str, str]:
    """Return {stop_id: stop_name} for stops whose normalized name contains (or equals, if exact) query."""
    normalized_query = normalize(query)
    if exact:
        return {
            stop_id: stop_name
            for stop_id, stop_name in data.stops.items()
            if normalize(stop_name) == normalized_query
        }
    return {
        stop_id: stop_name
        for stop_id, stop_name in data.stops.items()
        if normalized_query in normalize(stop_name)
    }


def search_stop_names(data_sets: list[GtfsStatic], query: str, limit: int = 20) -> list[str]:
    """Unique stop names across feeds matching query, prefix matches first, then alphabetical."""
    normalized_query = normalize(query)
    if not normalized_query:
        return []
    names = {
        name
        for data in data_sets
        for name in data.stops.values()
        if normalized_query in normalize(name)
    }
    ranked = sorted(
        names,
        key=lambda n: (not normalize(n).startswith(
            normalized_query), normalize(n)),
    )
    return ranked[:limit]
