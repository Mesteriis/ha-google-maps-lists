import asyncio
from datetime import datetime,UTC
from homeassistant.core import HomeAssistant
from custom_components.google_maps_lists.runtime import Runtime
from custom_components.google_maps_lists.catalog import Catalog
from custom_components.google_maps_lists.source import SourceError
from test_catalog import cfg,snap,NOW

def test_sequential_refresh_one_failure_does_not_block_other(tmp_path):
 async def case():
  h=HomeAssistant(str(tmp_path));c=Catalog(h,cfg(),lambda:NOW)
  class Source:
   async def async_fetch(self,row):
    if row.id=='one':raise SourceError('source_timeout')
    return snap('two')
  r=Runtime(h,cfg(),c,Source());await r.async_refresh()
  assert c.serialize()['groups'][0]['error']=='source_timeout'
  assert c.serialize()['groups'][1]['count']==1
  await r.async_stop()
 asyncio.run(case())
def test_reload_during_fetch_and_shutdown_cancel(tmp_path):
 async def case():
  h=HomeAssistant(str(tmp_path));c=Catalog(h,cfg(),lambda:NOW);began=asyncio.Event();cancelled=asyncio.Event()
  class Source:
   async def async_fetch(self,row):
    began.set()
    try:await asyncio.Event().wait()
    finally:cancelled.set()
  r=Runtime(h,cfg(),c,Source());r.task=asyncio.create_task(r.async_refresh());await asyncio.wait_for(began.wait(),1)
  await r.async_reconfigure(cfg(('two',)))
  assert cancelled.is_set() and c.serialize()['places']==[]
  assert [g['id'] for g in c.serialize()['groups']]==['two']
  await r.async_stop()
 asyncio.run(case())
def test_manual_refresh_debounce(tmp_path):
 async def case():
  h=HomeAssistant(str(tmp_path));c=Catalog(h,cfg(('one',)),lambda:NOW)
  class Source:
   def __init__(self):self.calls=0
   async def async_fetch(self,row):self.calls+=1;return snap()
  source=Source();r=Runtime(h,cfg(('one',)),c,source)
  await r.async_refresh(manual=True);await r.async_refresh(manual=True)
  assert source.calls==1
  await r.async_stop()
 asyncio.run(case())

def test_error_record_failure_is_visible_and_recovery_notifies(tmp_path):
 async def case():
  h=HomeAssistant(str(tmp_path));c=Catalog(h,cfg(('one',)),lambda:NOW)
  class Source:
   async def async_fetch(self,row):raise SourceError('source_timeout')
  r=Runtime(h,cfg(('one',)),c,Source());events=[];c.subscribe(events.append)
  save=c.store.async_save
  async def fail(*args):raise OSError('synthetic disk failure')
  c.store.async_save=fail
  await r.async_refresh()
  assert r.collection_error=='cache_write_failed' and len(events)==1
  c.store.async_save=save
  await r.async_refresh()
  assert r.collection_error is None and len(events)==3
  await r.async_stop()
 asyncio.run(case())
