"""Strict YAML configuration and source URL policy."""
import re
from urllib.parse import urlsplit, urlunsplit, unquote
import voluptuous as vol
from homeassistant.helpers import config_validation as cv
from .models import IntegrationConfig, ListConfig

LIST_TOKEN = re.compile(r"!2s([a-zA-Z0-9_-]+)!3e[0-9]+")

def source_url(value):
    if not isinstance(value, str):
        raise vol.Invalid("Expected a Google Maps view URL")
    parsed = urlsplit(value)
    if (parsed.scheme != "https" or parsed.username or parsed.password
            or parsed.port not in (None, 443) or parsed.fragment):
        raise vol.Invalid("Invalid view URL")
    short = parsed.hostname == "maps.app.goo.gl" and re.fullmatch(r"/[a-zA-Z0-9]+", parsed.path) and not parsed.query
    canonical = (parsed.hostname == "www.google.com" and parsed.path.startswith("/maps/")
                 and LIST_TOKEN.search(unquote(value)) and "invite" not in value.lower()
                 and "/preview/" not in parsed.path)
    if not (short or canonical):
        raise vol.Invalid("Expected a shared list view link")
    return urlunsplit(("https", parsed.hostname, parsed.path, parsed.query, ""))

_LIST = vol.Schema({vol.Required("id"): vol.All(cv.string, vol.Match(r"^[a-z0-9_]+$")),
    vol.Required("url"): source_url, vol.Optional("name"): cv.string,
    vol.Optional("icon", default="mdi:map-marker-outline"): vol.All(cv.string, vol.Match(r"^mdi:[a-z0-9-]+$")),
    vol.Optional("color"): vol.All(cv.string, vol.Match(r"^#[0-9a-fA-F]{6}$"))})
def place_label(value):
    if not isinstance(value, str) or not value.strip() or len(value) > 512:
        raise vol.Invalid("Label must be nonempty text, at most 512 characters")
    return value.strip()

_LABELS = vol.Schema({vol.Match(r"^-?[0-9]{1,20}:-?[0-9]{1,20}$"): place_label})
_SCHEMA = vol.Schema({vol.Optional("update_interval",default=21600): vol.All(cv.positive_int,vol.Range(min=60)),
    vol.Optional("stale_after",default=86400): vol.All(cv.positive_int,vol.Range(min=60)),
    vol.Optional("route_origin",default="zone.home"): vol.In(["zone.home"]),
    vol.Optional("notify_service",default="notify.mobile_app_phone"): vol.All(cv.string,vol.Match(r"^notify\.[a-z0-9_]+$")),
    vol.Optional("labels",default=dict): _LABELS,
    vol.Required("lists"): [_LIST]})

def validate_config(data):
    parsed = _SCHEMA(data)
    rows = tuple(ListConfig(**row) for row in parsed["lists"])
    if len({row.id for row in rows}) != len(rows) or len({row.url for row in rows}) != len(rows):
        raise vol.Invalid("List ids and view URLs must be unique")
    return IntegrationConfig(parsed["update_interval"],parsed["stale_after"],parsed["route_origin"],parsed["notify_service"],rows,tuple(parsed["labels"].items()))
