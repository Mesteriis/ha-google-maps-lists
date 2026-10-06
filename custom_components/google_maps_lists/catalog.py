"""Private durable per-list snapshots and deduplicated catalog projection."""
import asyncio
import colorsys
from copy import deepcopy
from dataclasses import asdict
from datetime import datetime, UTC, timedelta
import hashlib
import re
from homeassistant.helpers.storage import Store, UnsupportedStorageVersionError
from .const import PALETTE
from .models import valid_coordinates

ERROR_CODES = frozenset(('blocked_source','schema_changed','potentially_incomplete','source_unavailable',
    'source_timeout','response_too_large','too_many_redirects','cache_invalid','cache_write_failed'))

def fingerprint(url):
    return hashlib.sha256(url.encode()).hexdigest()


def _colors(config, previous):
    colors = dict(previous)
    occupied = {i.color.lower() for i in config.lists if i.color} | set(colors.values())
    for row in config.lists:
        if row.color:
            colors[row.id] = row.color.lower()
        elif row.id not in colors:
            next_color = next((c for c in PALETTE if c not in occupied),None)
            hue = 0
            while next_color is None:
                rgb = colorsys.hls_to_rgb((hue*137.508 % 360)/360,.66,.65)
                candidate = '#' + ''.join(f'{round(c*255):02x}' for c in rgb)
                hue += 1
                if candidate not in occupied:
                    next_color = candidate
            colors[row.id] = next_color
        occupied.add(colors[row.id])
    return colors


def _validate_state(data, now):
    if (not isinstance(data,dict) or set(data) != {'records','colors'}
            or not isinstance(data['records'],dict) or not isinstance(data['colors'],dict)):
        raise ValueError('cache_invalid')
    if any(not isinstance(k,str) or not isinstance(c,str) or not re.fullmatch(r'#[0-9a-f]{6}',c)
           for k,c in data['colors'].items()):
        raise ValueError('cache_invalid')
    for key,rec in data['records'].items():
        if (not isinstance(key,str) or not isinstance(rec,dict)
                or set(rec) != {'fingerprint','snapshot','error'}
                or not isinstance(rec['fingerprint'],str) or not re.fullmatch(r'[0-9a-f]{64}',rec['fingerprint'])
                or rec['error'] not in ERROR_CODES | {None}):
            raise ValueError('cache_invalid')
        snap = rec['snapshot']
        if snap is None:
            continue
        if not isinstance(snap,dict) or set(snap) != {'list_id','title','places','fetched_at'} or snap['list_id'] != key or not isinstance(snap['title'],str) or not isinstance(snap['places'],list):
            raise ValueError('cache_invalid')
        at = datetime.fromisoformat(snap['fetched_at'])
        if at.tzinfo is None or at > now + timedelta(minutes=5):
            raise ValueError('cache_invalid')
        ids = set()
        for p in snap['places']:
            if not isinstance(p,dict) or set(p) != {'id','name','address','note','latitude','longitude','google_maps_url'}:
                raise ValueError('cache_invalid')
            if any(not isinstance(p[x],str) for x in ('id','name','address','note','google_maps_url')) or not re.fullmatch(r'-?[0-9]+:-?[0-9]+',p['id']) or p['id'] in ids:
                raise ValueError('cache_invalid')
            if (p['latitude'],p['longitude']) != (None,None) and not valid_coordinates(p['latitude'],p['longitude']):
                raise ValueError('cache_invalid')
            if not p['google_maps_url'].startswith('https://www.google.com/maps/search/?api=1&query='):
                raise ValueError('cache_invalid')
            ids.add(p['id'])
    return data


class CheckedStore(Store):
    """Require a completed durable write: HA Store logs native failures internally.

    This wrapper is covered against the installed HA native write path. Catalog
    serializes all writes; no delayed saves are used by this integration.
    """
    async def _async_write_data(self, data):
        await super()._async_write_data(data)
        self._write_completed = True

    async def async_save(self, data):
        self._write_completed = False
        await super().async_save(data)
        if not self._write_completed:
            raise OSError('cache_write_failed')


class Catalog:
    def __init__(self,hass,config,clock=None):
        self.config = config
        self.clock = clock or (lambda:datetime.now(UTC))
        self.store = CheckedStore(hass,1,'google_maps_lists.catalog',private=True,atomic_writes=True)
        self._lock = asyncio.Lock()
        self._state = {'records':{},'colors':_colors(config,{})}
        self.revision = 0
        self._listeners = set()

    def subscribe(self,callback):
        self._listeners.add(callback)
        return lambda:self._listeners.discard(callback)

    def _notify(self):
        self.revision += 1
        for fn in tuple(self._listeners):
            fn(self.revision)

    def notify_status(self):
        self._notify()

    async def async_load(self):
        try:
            data = await self.store.async_load()
        except (UnsupportedStorageVersionError, NotImplementedError, KeyError, TypeError) as err:
            raise ValueError('cache_invalid') from err
        if data is None:
            return
        try:
            _validate_state(data,self.clock())
        except (TypeError,KeyError,ValueError) as err:
            raise ValueError('cache_invalid') from err
        self._state = self._reconfigured(data,self.config)
        self._notify()

    @staticmethod
    def _reconfigured(data,config):
        rows = {r.id:r for r in config.lists}
        records = {k:v for k,v in data['records'].items()
                   if k in rows and v['fingerprint'] == fingerprint(rows[k].url)}
        return {'records':records,'colors':_colors(config,data['colors'])}

    async def async_reconfigure(self,config):
        async with self._lock:
            state = self._reconfigured(self._state,config)
            await self.store.async_save(state)
            self._state,self.config = state,config
            self._notify()

    async def async_publish(self,snapshot,source_url=None):
        async with self._lock:
            row = next((r for r in self.config.lists if r.id == snapshot.list_id),None)
            if row is None or (source_url is not None and source_url != row.url):
                return
            data = asdict(snapshot)
            data['fetched_at'] = snapshot.fetched_at.isoformat()
            data['places'] = list(data['places'])
            state = deepcopy(self._state)
            state['records'][row.id] = {'fingerprint':fingerprint(row.url),'snapshot':data,'error':None}
            _validate_state(state,self.clock())
            await self.store.async_save(state)
            self._state = state
            self._notify()

    async def async_record_error(self,list_id,code):
        if code not in ERROR_CODES:
            raise ValueError('Unknown safe error code')
        async with self._lock:
            row = next((r for r in self.config.lists if r.id == list_id),None)
            if row is None:
                return
            state = deepcopy(self._state)
            rec = state['records'].setdefault(list_id,{'fingerprint':fingerprint(row.url),'snapshot':None,'error':None})
            rec['error'] = code
            await self.store.async_save(state)
            self._state = state
            self._notify()

    def serialize(self):
        groups, places = [], {}
        for row in self.config.lists:
            rec = self._state['records'].get(row.id,{})
            snap = rec.get('snapshot')
            at = snap['fetched_at'] if snap else None
            stale = not at or (self.clock()-datetime.fromisoformat(at)).total_seconds() >= self.config.stale_after
            color = self._state['colors'][row.id]
            collision = sum(self._state['colors'].get(r.id)==color for r in self.config.lists)>1
            groups.append({'id':row.id,'name':row.name or (snap['title'] if snap else row.id),
                'icon':row.icon,'color':color,'count':len(snap['places']) if snap else 0,
                'last_success':at,'stale':bool(stale),'error':rec.get('error'),
                'color_collision':collision})
            if not snap:
                continue
            for p in snap['places']:
                if p['id'] not in places:
                    places[p['id']] = {k:v for k,v in p.items() if k != 'note'}
                    places[p['id']]['memberships'] = []
                elif places[p['id']]['latitude'] is None and p['latitude'] is not None:
                    places[p['id']]['latitude'] = p['latitude']
                    places[p['id']]['longitude'] = p['longitude']
                    places[p['id']]['google_maps_url'] = p['google_maps_url']
                places[p['id']]['memberships'].append({'list_id':row.id,'note':p['note']})
        for place_id, label in self.config.labels:
            if place_id in places:
                places[place_id]['label'] = label
        return {'version':1,'revision':self.revision,'groups':groups,'places':list(places.values())}

    def get_place(self,place_id):
        return next((p for p in self.serialize()['places'] if p['id']==place_id),None)
