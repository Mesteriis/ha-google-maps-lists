import asyncio
import json
from types import SimpleNamespace
import pytest
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from custom_components.google_maps_lists.details import feature_id, details_url, photo_url, parse_details
from custom_components.google_maps_lists.source import SourceError, validate_request_url
from custom_components.google_maps_lists.catalog import Catalog
from custom_components.google_maps_lists.runtime import Runtime
from test_catalog import cfg, snap, NOW

PHOTO = 'https://lh3.googleusercontent.com/gps-cs-s/Example_photo=w960-h600-k-no'

def payload(identity='0x64:0xc8', photo=PHOTO, gallery=True):
    record = [None]*38; record[10] = identity
    if gallery:
        item = [None]*16; item[6] = [photo]; item[15] = [[[identity]]]
        record[37] = [[item]]
    data = [None]*7; data[6] = record
    return b")]}'\n" + json.dumps(data).encode()


def test_identity_and_gallery():
    assert parse_details(payload(), '100:200') == {'photo_url':PHOTO}
    assert parse_details(payload(photo=PHOTO.replace('w960-h600','w208-h360')+'-pi-0-ya191'),'100:200')['photo_url']==PHOTO+'-pi-0-ya191'
    assert parse_details(payload(gallery=False), '100:200') == {'photo_url':None}
    with pytest.raises(SourceError):parse_details(payload('0x64:0xc9'), '100:200')
    with pytest.raises(SourceError):parse_details(b'not-json','100:200')
    empty=json.loads(payload()[5:]);empty[6][37]=[None]
    assert parse_details(b")]}'\n"+json.dumps(empty).encode(),'100:200')=={'photo_url':None}

@pytest.mark.parametrize('url', ['https://lh3.googleusercontent.com/a-/author',
    'https://evil.test/gps-cs-s/photo','http://lh3.googleusercontent.com/p/photo',
    'https://lh3.googleusercontent.com:443/p/photo','https://user@lh3.googleusercontent.com/p/photo',
    'https://lh3.googleusercontent.com/p/photo#fragment'])
def test_photo_allowlist_excludes_avatars_and_foreign_sources(url):
    assert photo_url(url) is None
    assert parse_details(payload(photo=url),'100:200')['photo_url'] is None


def test_details_source_url_has_only_public_identity():
    assert feature_id('-1:200') == '0xffffffffffffffff:0xc8'
    url = details_url('100:200')
    assert validate_request_url(url,'details') == url
    with pytest.raises(SourceError):validate_request_url('https://www.google.com/maps/preview/entitylist/getlist','details')
    with pytest.raises(SourceError):validate_request_url('https://accounts.google.com/maps/preview/place','details')
    for value in ('url','100:200&authuser=1','18446744073709551616:200'):
        with pytest.raises(SourceError):details_url(value)


def test_cache_unknown_place_and_single_flight(tmp_path):
    async def case():
        h=HomeAssistant(str(tmp_path)); c=Catalog(h,cfg(('one',)),lambda:NOW)
        await c.async_publish(snap())
        class Source:
            calls=0
            async def async_details(self, place_id):
                self.calls+=1; await asyncio.sleep(0)
                return {'photo_url':PHOTO}
        source=Source();r=Runtime(h,cfg(('one',)),c,source)
        with pytest.raises(ServiceValidationError):await r.async_details('unknown')
        a,b=await asyncio.gather(r.async_details('100:200'),r.async_details('100:200'))
        assert a==b=={'photo_url':PHOTO} and source.calls==1
        a['photo_url']='changed'
        assert (await r.async_details('100:200'))['photo_url']==PHOTO
        await r.async_stop()
    asyncio.run(case())


def test_error_cooldown_and_shutdown(tmp_path):
    async def case():
        h=HomeAssistant(str(tmp_path));c=Catalog(h,cfg(('one',)),lambda:NOW);await c.async_publish(snap())
        class Source:
            calls=0
            async def async_details(self, place_id):
                self.calls+=1;raise SourceError('source_timeout')
        source=Source();r=Runtime(h,cfg(('one',)),c,source)
        for _ in range(2):
            with pytest.raises(SourceError):await r.async_details('100:200')
        assert source.calls==1
        began=asyncio.Event()
        async def wait(place_id):
            began.set(); await asyncio.Event().wait()
        r._details_cache.clear();source.async_details=wait
        task=asyncio.create_task(r.async_details('100:200'));await began.wait();await r.async_stop()
        assert task.cancelled() and not r._details_tasks
    asyncio.run(case())


def test_reconfigure_fences_inflight_details(tmp_path):
    async def case():
        h=HomeAssistant(str(tmp_path));c=Catalog(h,cfg(('one',)),lambda:NOW);await c.async_publish(snap())
        began=asyncio.Event();release=asyncio.Event()
        class Source:
            async def async_details(self, place_id):
                began.set();await release.wait();return {'photo_url':PHOTO}
        r=Runtime(h,cfg(('one',)),c,Source())
        task=asyncio.create_task(r.async_details('100:200'));await began.wait()
        await r.async_reconfigure(cfg(('two',)));release.set()
        with pytest.raises(ServiceValidationError):await task
        assert not r._details_cache
        await r.async_stop()
    asyncio.run(case())


def test_bounded_cache(tmp_path):
    async def case():
        class Source:
            async def async_details(self, place_id):return {'photo_url':PHOTO}
        r=Runtime(HomeAssistant(str(tmp_path)),cfg(),SimpleNamespace(get_place=lambda key:{'id':key}),Source())
        for i in range(70):await r.async_details(f'100:{i}')
        assert len(r._details_cache)==64 and '100:0' not in r._details_cache
        await r.async_stop()
    asyncio.run(case())
