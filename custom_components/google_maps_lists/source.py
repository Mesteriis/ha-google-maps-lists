"""Bounded anonymous Google view-link reader. Never execute page scripts."""
import asyncio
from datetime import datetime, UTC
from html.parser import HTMLParser
import json
import re
from urllib.parse import urlsplit, urljoin, unquote, urlencode, parse_qsl, urlunsplit
import aiohttp
from .config import LIST_TOKEN
from .models import ListSnapshot, SourcePlace, valid_coordinates

class SourceError(Exception):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def validate_request_url(url, kind):
    try:
        u = urlsplit(url)
        if u.scheme != "https" or u.username or u.password or u.port not in (None, 443) or u.fragment:
            raise SourceError("blocked_source")
        if kind == "details":
            valid = u.hostname == "www.google.com" and u.path == "/maps/preview/place"
        elif kind == "json":
            valid = u.hostname == "www.google.com" and u.path == "/maps/preview/entitylist/getlist"
        else:
            short = u.hostname == "maps.app.goo.gl" and re.fullmatch(r"/[a-zA-Z0-9]+", u.path) and not u.query
            page = (u.hostname == "www.google.com" and u.path.startswith("/maps/")
                    and "/preview/" not in u.path and LIST_TOKEN.search(unquote(url)))
            valid = short or page
        if not valid:
            raise SourceError("blocked_source")
    except ValueError as err:
        raise SourceError("blocked_source") from err
    return url


class PreloadReader(HTMLParser):
    def __init__(self):
        super().__init__()
        self.urls = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        href = attrs.get("href", "")
        if tag == "link" and attrs.get("rel") == "preload" and "/maps/preview/entitylist/getlist?" in href:
            self.urls.append(href)


def _text(value):
    if value is None:
        return ""
    if not isinstance(value, str):
        raise SourceError("schema_changed")
    return value


def _place(item):
    detail = item[1]
    feature = detail[6]
    if not isinstance(feature, list) or len(feature) != 2 or any(not isinstance(i,str) or not re.fullmatch(r"-?[0-9]+",i) for i in feature):
        raise SourceError("schema_changed")
    coords = detail[5]
    lat, lon = (None, None) if coords is None else coords[2:4]
    if (lat, lon) != (None, None) and not valid_coordinates(lat, lon):
        raise SourceError("schema_changed")
    name, address, note = _text(item[2]), _text(detail[4]), _text(item[3])
    if not name:
        raise SourceError("schema_changed")
    query = f"{lat},{lon}" if lat is not None else f"{name} {address}".strip()
    return SourcePlace(":".join(feature), name, address, note, lat, lon,
                       "https://www.google.com/maps/search/?" + urlencode({"api":1,"query":query}))


def parse_getlist(payload, list_id, expected_google_list_id, fetched_at):
    try:
        if not payload.startswith(b")]}'\n"):
            raise SourceError("schema_changed")
        data = json.loads(payload[5:])
        row = data[0]
        if row[0][0] != expected_google_list_id or not isinstance(row[4],str) or not isinstance(row[8],list):
            raise SourceError("schema_changed")
        if len(row[8]) >= 500:
            raise SourceError("potentially_incomplete")
        places = tuple(_place(item) for item in row[8])
        if len({p.id for p in places}) != len(places):
            raise SourceError("schema_changed")
        return ListSnapshot(list_id,row[4],places,fetched_at)
    except (ValueError, KeyError, TypeError, IndexError) as err:
        raise SourceError("schema_changed") from err


class GoogleListSource:
    def __init__(self, session):
        self.session = session

    async def _get(self, url, kind):
        cap = 8*1024*1024 if kind == "json" else 4*1024*1024
        for _ in range(6):
            validate_request_url(url,kind)
            async with self.session.get(url,allow_redirects=False,
                headers={"User-Agent":"Mozilla/5.0", "Referer":"https://www.google.com/maps/"},
                timeout=aiohttp.ClientTimeout(total=30,connect=10)) as response:
                if response.status in (301,302,303,307,308):
                    location = response.headers.get("Location")
                    if not location:
                        raise SourceError("blocked_source")
                    next_url = urljoin(url,location)
                    # Google anonymous view sometimes bounces through consent. Request
                    # the same allowlisted list page with its public no-cookie flag;
                    # never visit the consent host or submit consent/account actions.
                    u = urlsplit(url)
                    if (kind == "page" and u.hostname == "www.google.com"
                            and urlsplit(next_url).hostname == "consent.google.com"
                            and "ucbcb" not in dict(parse_qsl(u.query))):
                        query = parse_qsl(u.query) + [("ucbcb","1")]
                        next_url = urlunsplit((u.scheme,u.netloc,u.path,urlencode(query),""))
                    url = next_url
                    continue
                if response.status != 200:
                    raise SourceError("source_unavailable")
                buf = bytearray()
                async for chunk in response.content.iter_chunked(65536):
                    buf.extend(chunk)
                    if len(buf) > cap:
                        raise SourceError("response_too_large")
                return bytes(buf),url
        raise SourceError("too_many_redirects")

    async def async_fetch(self, config):
        try:
            async with asyncio.timeout(30):
                body,canonical = await self._get(config.url,"page")
                match = LIST_TOKEN.search(unquote(canonical))
                if not match:
                    raise SourceError("schema_changed")
                reader = PreloadReader()
                reader.feed(body.decode("utf-8"))
                if len(reader.urls) != 1:
                    raise SourceError("schema_changed")
                payload,_ = await self._get(urljoin(canonical,reader.urls[0]),"json")
                return parse_getlist(payload,config.id,match.group(1),datetime.now(UTC))
        except TimeoutError as err:
            raise SourceError("source_timeout") from err
        except (aiohttp.ClientError,UnicodeError) as err:
            raise SourceError("source_unavailable") from err

    async def async_details(self, place_id):
        from .details import details_url, parse_details
        try:
            async with asyncio.timeout(30):
                body, _ = await self._get(details_url(place_id), "details")
                return parse_details(body, place_id)
        except TimeoutError as err:
            raise SourceError("source_timeout") from err
        except (aiohttp.ClientError, UnicodeError) as err:
            raise SourceError("source_unavailable") from err
