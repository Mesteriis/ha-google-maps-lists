import asyncio
from types import SimpleNamespace
from urllib.parse import urlsplit,parse_qs
import pytest
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from custom_components.google_maps_lists.routes import RouteActions
from custom_components.google_maps_lists.catalog import Catalog
from test_catalog import cfg,snap,NOW

def test_live_home_each_action(tmp_path):
 async def case():
  h=HomeAssistant(str(tmp_path));c=Catalog(h,cfg(),lambda:NOW);await c.async_publish(snap())
  r=RouteActions(h,c,cfg());h.states.async_set('zone.home','0',{'latitude':41.5,'longitude':2.5})
  q=parse_qs(urlsplit(r.build_url('100:200','transit')).query)
  assert q=={'api':['1'],'origin':['41.5,2.5'],'destination':['41,2'],'travelmode':['transit']}
  h.states.async_set('zone.home','0',{'latitude':42,'longitude':3})
  assert parse_qs(urlsplit(r.build_url('100:200','walking')).query)['origin']==['42,3']
 asyncio.run(case())

@pytest.mark.parametrize('id,mode', [('missing','transit'),('100:200','spaceship')])
def test_unknown_place_mode(tmp_path,id,mode):
 async def case():
  h=HomeAssistant(str(tmp_path));c=Catalog(h,cfg(),lambda:NOW);await c.async_publish(snap())
  h.states.async_set('zone.home','0',{'latitude':41,'longitude':2})
  with pytest.raises(ServiceValidationError):RouteActions(h,c,cfg()).build_url(id,mode)
 asyncio.run(case())

@pytest.mark.parametrize('state,attrs',[(None,{}),('unavailable',{'latitude':41,'longitude':2}),('0',{'latitude':float('nan'),'longitude':2})])
def test_home_unavailable(tmp_path,state,attrs):
 async def case():
  h=HomeAssistant(str(tmp_path));c=Catalog(h,cfg(),lambda:NOW);await c.async_publish(snap())
  if state is not None:h.states.async_set('zone.home',state,attrs)
  with pytest.raises(ServiceValidationError):RouteActions(h,c,cfg()).build_url('100:200','transit')
 asyncio.run(case())

def test_notification_target_bound_and_failure(tmp_path):
 async def case():
  h=HomeAssistant(str(tmp_path));c=Catalog(h,cfg(),lambda:NOW);await c.async_publish(snap())
  h.states.async_set('zone.home','0',{'latitude':41,'longitude':2});received=[]
  async def notify(call):received.append(dict(call.data))
  h.services.async_register('notify','mobile_app_phone',notify)
  r=RouteActions(h,c,cfg());await r.async_send('100:200','driving')
  assert len(received)==1 and received[0]['data']['url']==received[0]['data']['clickAction']
  assert received[0]['data']['actions'][0]['uri']==received[0]['data']['url']
  async def broken(call):raise RuntimeError('private failure')
  h.services.async_register('notify','mobile_app_phone',broken)
  with pytest.raises(ServiceValidationError) as e:await r.async_send('100:200','driving')
  assert 'private' not in str(e.value)
 asyncio.run(case())
