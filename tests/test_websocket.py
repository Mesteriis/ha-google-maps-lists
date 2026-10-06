import asyncio
from types import SimpleNamespace
import pytest
import voluptuous as vol
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import Unauthorized
from custom_components.google_maps_lists.websocket import ws_catalog,ws_subscribe
from custom_components.google_maps_lists.routes import ACTION_SCHEMA
from custom_components.google_maps_lists.catalog import Catalog
from test_catalog import cfg,snap,NOW

class Connection:
 def __init__(self,user=True):self.user=SimpleNamespace(is_admin=False) if user else None;self.subscriptions={};self.results=[];self.events=[]
 def send_result(self,*v):self.results.append(v)
 def send_event(self,*v):self.events.append(v)

def test_read_requires_authenticated_connection(tmp_path):
 async def case():
  h=HomeAssistant(str(tmp_path));h.data['google_maps_lists']=SimpleNamespace(catalog=Catalog(h,cfg(),lambda:NOW),collection_error=None)
  with pytest.raises(Unauthorized):ws_catalog(h,Connection(False),{'id':1})
 asyncio.run(case())

def test_subscription_cleanup(tmp_path):
 async def case():
  h=HomeAssistant(str(tmp_path));catalog=Catalog(h,cfg(),lambda:NOW);h.data['google_maps_lists']=SimpleNamespace(catalog=catalog)
  conn=Connection();ws_subscribe(h,conn,{'id':1})
  await catalog.async_publish(snap());assert len(conn.events)==2
  conn.subscriptions.pop(1)();await catalog.async_record_error('one','source_timeout')
  assert len(conn.events)==2
 asyncio.run(case())

@pytest.mark.parametrize('extra',['url','origin','notify_service'])
def test_extra_authority_fields_rejected(extra):
 with pytest.raises(vol.Invalid):ACTION_SCHEMA({'place_id':'100:200','mode':'transit',extra:'malicious'})

def test_reconnect_subscription_starts_with_current_revision(tmp_path):
 async def case():
  h=HomeAssistant(str(tmp_path));c=Catalog(h,cfg(),lambda:NOW);h.data['google_maps_lists']=SimpleNamespace(catalog=c)
  conn=Connection();ws_subscribe(h,conn,{'id':1})
  assert conn.results==[(1,)] and conn.events==[(1,{'revision':c.revision})]
  conn.subscriptions.pop(1)()
  await c.async_reconfigure(cfg(('two',)))
  ws_subscribe(h,conn,{'id':2})
  assert conn.events[-1]==(2,{'revision':c.revision})
 asyncio.run(case())


def test_details_authenticated_protocol_and_error(tmp_path):
 from custom_components.google_maps_lists.websocket import ws_details
 async def case():
  h=HomeAssistant(str(tmp_path))
  class Runtime:
   async def async_details(self, place_id):
    if place_id!='100:200':
     from homeassistant.exceptions import ServiceValidationError
     raise ServiceValidationError('unknown_place')
    return {'photo_url':None}
  h.data['google_maps_lists']=Runtime()
  with pytest.raises(Unauthorized):await ws_details.__wrapped__(h,Connection(False),{'id':1,'place_id':'100:200'})
  conn=Connection();errors=[];conn.send_error=lambda *args:errors.append(args)
  await ws_details.__wrapped__(h,conn,{'id':1,'place_id':'100:200'})
  assert conn.results==[(1,{'photo_url':None})]
  await ws_details.__wrapped__(h,conn,{'id':2,'place_id':'unknown'})
  assert errors==[(2,'unknown_place','unknown_place')]
 asyncio.run(case())
