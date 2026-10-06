"""Lazy public place thumbnails; no private labels, avatars or review harvesting."""
import json
import re
from urllib.parse import urlencode, urlsplit
from .source import SourceError


def feature_id(place_id):
    if not isinstance(place_id, str) or not re.fullmatch(r"-?[0-9]{1,20}:-?[0-9]{1,20}", place_id):
        raise SourceError("schema_changed")
    values = [int(v) for v in place_id.split(":")]
    if any(v < -(1 << 63) or v >= (1 << 64) for v in values):
        raise SourceError("schema_changed")
    return ":".join(hex(v % (1 << 64)) for v in values)


def details_url(place_id):
    return "https://www.google.com/maps/preview/place?" + urlencode({
        "pb": "!1m1!1s" + feature_id(place_id) + "!12m4!2m3!1i640!2i360!4i8", "hl": "ru"})


def photo_url(value):
    if not isinstance(value, str) or len(value) > 2048:
        return None
    try:
        u = urlsplit(value)
        if (u.scheme == "https" and re.fullmatch(r"lh[3-6]\.googleusercontent\.com", u.hostname or "")
                and not u.username and not u.password and u.port is None and not u.fragment
                and re.match(r"^/(p|gps-cs-s)/[A-Za-z0-9_-]+", u.path)):
            return value
    except ValueError:
        pass
    return None


def parse_details(payload, place_id):
    try:
        if not payload.startswith(b")]}'\n"):
            raise SourceError("schema_changed")
        record = json.loads(payload[5:])[6]
        expected = feature_id(place_id)
        if record[10] != expected:
            raise SourceError("schema_changed")
        photo = None
        gallery = record[37] if len(record) > 37 else None
        if gallery is not None:
            if isinstance(gallery, list) and (not gallery or gallery[0] is None):
                return {"photo_url": None}
            if not isinstance(gallery, list) or not isinstance(gallery[0], list):
                raise SourceError("schema_changed")
            for item in gallery[0][:8]:
                # These are this place's public gallery rows, not contributor avatars.
                if item[15][0][0][0] != expected:
                    continue
                photo = photo_url(item[6][0])
                if photo:
                    # Preserve Google panorama framing; request adequate display resolution.
                    photo = re.sub(r"=w[0-9]+-h[0-9]+", "=w960-h600", photo, count=1)
                    break
        return {"photo_url": photo}
    except (ValueError, TypeError, IndexError, KeyError) as err:
        raise SourceError("schema_changed") from err
