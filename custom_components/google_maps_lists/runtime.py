"""HA-owned sequential collection, scheduling and YAML reload lifecycle."""
import asyncio
from collections import OrderedDict
from homeassistant.exceptions import ServiceValidationError
from datetime import timedelta
import logging
import time
from homeassistant.core import callback
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.reload import async_integration_yaml_config
from .config import validate_config
from .const import DOMAIN
from .source import SourceError

LOGGER = logging.getLogger(__name__)

class Runtime:
    def __init__(self,hass,config,catalog,source):
        self.hass,self.config,self.catalog,self.source = hass,config,catalog,source
        self.task = None
        self.cancel_timer = None
        self.cancel_start = None
        self.session = None
        self.stopping = False
        self._collection = asyncio.Lock()
        self._reload = asyncio.Lock()
        self._generation = 0
        self._last_manual = float('-inf')
        self.collection_error = None
        self._details_lock = asyncio.Lock()
        self._details_cache = OrderedDict()
        self._details_tasks = set()

    @callback
    def start(self,event=None):
        if not self.stopping and self.hass.is_running and (self.task is None or self.task.done()):
            self.task = self.hass.async_create_background_task(self.async_refresh(),f'{DOMAIN} refresh')

    def schedule(self):
        if self.cancel_timer:
            self.cancel_timer()
        self.cancel_timer = async_track_time_interval(self.hass,self.start,
            timedelta(seconds=self.config.update_interval),name=DOMAIN,cancel_on_shutdown=True)

    async def async_refresh(self,manual=False):
        if self.stopping or self._collection.locked():
            return
        if manual:
            now = time.monotonic()
            if now-self._last_manual < 60:
                return
            self._last_manual = now
        async with self._collection:
            generation = self._generation
            for row in self.config.lists:
                try:
                    try:
                        snapshot = await self.source.async_fetch(row)
                    except SourceError as err:
                        if generation != self._generation:
                            return
                        await self.catalog.async_record_error(row.id,err.code)
                    else:
                        if generation != self._generation:
                            return
                        await self.catalog.async_publish(snapshot,source_url=row.url)
                except (OSError,ValueError):
                    self._set_collection_error('cache_write_failed')
                    LOGGER.error('Google list cache could not be updated')
                    return
            self._set_collection_error(None)

    async def async_details(self, place_id):
        if self.stopping or not self.catalog.get_place(place_id):
            raise ServiceValidationError('unknown_place')
        task = asyncio.current_task()
        self._details_tasks.add(task)
        generation = self._generation
        try:
            async with self._details_lock:
                if self.stopping or generation != self._generation or not self.catalog.get_place(place_id):
                    raise ServiceValidationError('unknown_place')
                cached = self._details_cache.get(place_id)
                if cached and cached[0] > time.monotonic():
                    self._details_cache.move_to_end(place_id)
                    if cached[2]:
                        raise SourceError(cached[2])
                    return dict(cached[1])
                try:
                    result = await self.source.async_details(place_id)
                except SourceError as err:
                    if generation == self._generation and self.catalog.get_place(place_id):
                        self._details_cache[place_id] = (time.monotonic()+60, None, err.code)
                    raise
                else:
                    if generation != self._generation or not self.catalog.get_place(place_id):
                        raise ServiceValidationError('unknown_place')
                    ttl = 3600 if result.get('photo_url') else 60
                    self._details_cache[place_id] = (time.monotonic()+ttl, dict(result), None)
                    return dict(result)
                finally:
                    while len(self._details_cache) > 64:
                        self._details_cache.popitem(last=False)
        finally:
            self._details_tasks.discard(task)

    def _set_collection_error(self,code):
        if self.collection_error != code:
            self.collection_error = code
            self.catalog.notify_status()

    async def async_reload(self):
        yaml_config = await async_integration_yaml_config(self.hass,DOMAIN,raise_on_failure=True)
        if not yaml_config or DOMAIN not in yaml_config:
            raise ValueError('Configuration section missing')
        await self.async_reconfigure(validate_config(yaml_config[DOMAIN]))
        self.start()

    async def async_reconfigure(self,config):
        async with self._reload:
            self._generation += 1
            self._details_cache.clear()
            if self.task and not self.task.done():
                self.task.cancel()
                await asyncio.gather(self.task,return_exceptions=True)
            # An awaited manual service refresh may not be stored in self.task.
            async with self._collection:
                await self.catalog.async_reconfigure(config)
                self.config = config
            self.schedule()

    async def async_stop(self,event=None):
        self.stopping = True
        if self.cancel_timer:
            self.cancel_timer()
        if self.cancel_start:
            self.cancel_start()
        if self.task and not self.task.done():
            self.task.cancel()
            await asyncio.gather(self.task,return_exceptions=True)
        tasks = tuple(self._details_tasks)
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        self._details_cache.clear()
        if self.session:
            await self.session.close()
