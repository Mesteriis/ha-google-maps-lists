import asyncio
from copy import deepcopy
from datetime import datetime,UTC,timedelta
from pathlib import Path
import pytest
from homeassistant.core import HomeAssistant
from custom_components.google_maps_lists.config import validate_config
from custom_components.google_maps_lists.models import ListSnapshot,SourcePlace
from custom_components.google_maps_lists.catalog import Catalog

NOW=datetime(2026,10,6,tzinfo=UTC)
def cfg(ids=('one','two')):
 return validate_config({'lists':[{'id':i,'url':'https://maps.app.goo.gl/'+i} for i in ids]})
def snap(id='one',note='a',at=NOW):
 return ListSnapshot(id,'Test',(SourcePlace('100:200','Place','Street',note,41,2,'https://www.google.com/maps/search/?api=1&query=41%2C2'),),at)
def test_failure_keeps_snapshot_age(tmp_path):
 async def case():
  c=Catalog(HomeAssistant(str(tmp_path)),cfg(),lambda:NOW+timedelta(days=2))
  await c.async_publish(snap());await c.async_record_error('one','source_timeout')
  d=c.serialize();g=d['groups'][0]
  assert len(d['places'])==1 and g['stale'] and g['last_success']==NOW.isoformat() and g['error']=='source_timeout'
 asyncio.run(case())
def test_membership_notes_dedup(tmp_path):
 async def case():
  c=Catalog(HomeAssistant(str(tmp_path)),cfg(),lambda:NOW)
  await c.async_publish(snap());await c.async_publish(snap('two','second'))
  p=c.serialize()['places'];assert len(p)==1
  assert p[0]['memberships']==[{'list_id':'one','note':'a'},{'list_id':'two','note':'second'}]
 asyncio.run(case())
def test_restart_and_palette_survives_reorder(tmp_path):
 async def case():
  h=HomeAssistant(str(tmp_path));c=Catalog(h,cfg(),lambda:NOW)
  await c.async_publish(snap());old={g['id']:g['color'] for g in c.serialize()['groups']}
  c2=Catalog(h,cfg(('two','one','three')),lambda:NOW);await c2.async_load()
  assert len(c2.serialize()['places'])==1
  assert {g['id']:g['color'] for g in c2.serialize()['groups'] if g['id']!='three'}==old
 asyncio.run(case())
def test_changed_url_and_removed_source_cannot_publish(tmp_path):
 async def case():
  c=Catalog(HomeAssistant(str(tmp_path)),cfg(),lambda:NOW);await c.async_publish(snap())
  new=validate_config({'lists':[{'id':'one','url':'https://maps.app.goo.gl/new'}]})
  await c.async_reconfigure(new)
  await c.async_publish(snap(),source_url='https://maps.app.goo.gl/one')
  await c.async_publish(snap('two'),source_url='https://maps.app.goo.gl/two')
  assert c.serialize()['places']==[] and len(c.serialize()['groups'])==1
 asyncio.run(case())
def test_storage_failure_atomicity(tmp_path):
 async def case():
  c=Catalog(HomeAssistant(str(tmp_path)),cfg(),lambda:NOW);await c.async_publish(snap())
  before=deepcopy(c.serialize())
  async def fail(*args):raise OSError('disk')
  c.store.async_save=fail
  with pytest.raises(OSError):await c.async_publish(ListSnapshot('one','Empty',(),NOW))
  assert c.serialize()==before
 asyncio.run(case())
def test_confirmed_empty_replaces_success(tmp_path):
 async def case():
  c=Catalog(HomeAssistant(str(tmp_path)),cfg(),lambda:NOW);await c.async_publish(snap())
  await c.async_publish(ListSnapshot('one','Empty',(),NOW))
  assert c.serialize()['places']==[] and c.serialize()['groups'][0]['last_success']==NOW.isoformat()
 asyncio.run(case())
def test_corrupt_cache_not_published(tmp_path):
 async def case():
  c=Catalog(HomeAssistant(str(tmp_path)),cfg(),lambda:NOW)
  async def bad():return {'records':{'one':{'snapshot':{'private':'evil'}}}}
  c.store.async_load=bad
  with pytest.raises(ValueError):await c.async_load()
  assert c.serialize()['places']==[]
 asyncio.run(case())

def test_native_write_failure_does_not_publish(tmp_path):
 from homeassistant.util.file import WriteError
 async def case():
  c=Catalog(HomeAssistant(str(tmp_path)),cfg(),lambda:NOW);await c.async_publish(snap())
  before=deepcopy(c.serialize())
  def fail(*args):raise WriteError('synthetic write failure')
  c.store._write_prepared_data=fail
  with pytest.raises(OSError):await c.async_publish(ListSnapshot('one','Empty',(),NOW))
  assert c.serialize()==before
  with pytest.raises(OSError):await c.async_reconfigure(cfg(('two',)))
  assert c.serialize()==before
 asyncio.run(case())

@pytest.mark.parametrize('envelope',[{'version':99,'minor_version':1,'data':{}},{'version':0,'minor_version':1,'data':{}},{'data':{}}])
def test_native_unsupported_storage_is_safe_error(tmp_path,envelope):
 import json
 async def case():
  c=Catalog(HomeAssistant(str(tmp_path)),cfg(),lambda:NOW)
  path=Path(c.store.path);path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(envelope))
  with pytest.raises(ValueError,match='cache_invalid'):await c.async_load()
  assert json.loads(path.read_text())==envelope
  assert c.serialize()['places']==[]
 asyncio.run(case())

def test_duplicate_uses_available_coordinates(tmp_path):
 async def case():
  from dataclasses import replace
  c=Catalog(HomeAssistant(str(tmp_path)),cfg(),lambda:NOW)
  first=snap();first=replace(first,places=(replace(first.places[0],latitude=None,longitude=None),))
  await c.async_publish(first);await c.async_publish(snap('two','second'))
  place=c.serialize()['places'][0]
  assert (place['latitude'],place['longitude'])==(41,2)
  assert len(place['memberships'])==2
 asyncio.run(case())
