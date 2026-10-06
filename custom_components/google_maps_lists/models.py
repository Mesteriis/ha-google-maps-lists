"""Immutable, minimal shared-list records."""
from dataclasses import dataclass
from datetime import datetime
import math

@dataclass(frozen=True)
class ListConfig:
    id: str
    url: str
    name: str | None = None
    icon: str = "mdi:map-marker-outline"
    color: str | None = None

@dataclass(frozen=True)
class IntegrationConfig:
    update_interval: int
    stale_after: int
    route_origin: str
    notify_service: str
    lists: tuple[ListConfig, ...]
    labels: tuple[tuple[str, str], ...] = ()

@dataclass(frozen=True)
class SourcePlace:
    id: str
    name: str
    address: str
    note: str
    latitude: float | None
    longitude: float | None
    google_maps_url: str

@dataclass(frozen=True)
class ListSnapshot:
    list_id: str
    title: str
    places: tuple[SourcePlace, ...]
    fetched_at: datetime

def valid_coordinates(lat, lon):
    return (type(lat) in (int, float) and type(lon) in (int, float)
            and math.isfinite(lat) and math.isfinite(lon)
            and -90 <= lat <= 90 and -180 <= lon <= 180)
