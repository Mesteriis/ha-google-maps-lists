import asyncio
from types import SimpleNamespace
from unittest.mock import patch, AsyncMock
import pytest
from homeassistant.core import HomeAssistant,Context
from homeassistant.exceptions import Unauthorized
from custom_components.google_maps_lists import async_setup,CONFIG_SCHEMA
from custom_components.google_maps_lists.sensor import CatalogStatus
from test_catalog import cfg,NOW,snap


def test_setup_no_network_before_start_sensor_counts_and_admin_reload(tmp_path):
 async def case():
  h=HomeAssistant(str(tmp_path));commands=[]
  async def no_platform(*args):pass
  async def get_user(uid):return SimpleNamespace(is_admin=False)
  h.auth=SimpleNamespace(async_get_user=get_user)
  config={'google_maps_lists':{'lists':[{'id':'one','url':'https://maps.app.goo.gl/one'}]}}
  with patch('custom_components.google_maps_lists.frontend.async_register_card',new_callable=AsyncMock), patch('custom_components.google_maps_lists.async_load_platform',no_platform),patch('homeassistant.components.websocket_api.async_register_command',lambda h,c:commands.append(c)):
   assert CONFIG_SCHEMA(config)==config
   assert await async_setup(h,config)
   assert len(commands)==5 and len(h.data['google_maps_lists'].catalog.serialize()['places'])==0
   r=h.data['google_maps_lists'];sensor=CatalogStatus(r);await sensor.async_update()
   assert sensor.native_value==0
   assert set(sensor.extra_state_attributes)=={'source_count','stale_count','error_count','collection_error'}
   with pytest.raises(Unauthorized):await h.services.async_call('google_maps_lists','reload',{},blocking=True,context=Context(user_id='test-viewer'))
   assert await async_setup(h,config) and len(commands)==5
   await r.async_stop()
   assert r.session.closed
 asyncio.run(case())

@pytest.mark.parametrize('envelope',[{'version':99,'minor_version':1,'data':{}},{'version':0,'minor_version':1,'data':{}},{'data':{}}])
def test_bad_native_cache_is_preserved_and_setup_continues(tmp_path,envelope):
 import json
 from pathlib import Path
 async def case():
  h=HomeAssistant(str(tmp_path));path=Path(tmp_path)/'.storage/google_maps_lists.catalog';path.parent.mkdir();path.write_text(json.dumps(envelope))
  async def no_platform(*args):pass
  with patch('custom_components.google_maps_lists.frontend.async_register_card',new_callable=AsyncMock), patch('custom_components.google_maps_lists.async_load_platform',no_platform),patch('homeassistant.components.websocket_api.async_register_command',lambda *args:None):
   assert await async_setup(h,{'google_maps_lists':{'lists':[{'id':'one','url':'https://maps.app.goo.gl/one'}]}})
   r=h.data['google_maps_lists']
   assert r.catalog.serialize()['groups'][0]['error']=='cache_invalid'
   copies=list(path.parent.glob('google_maps_lists.catalog.invalid-*'))
   assert len(copies)==1 and json.loads(copies[0].read_text())==envelope
   assert copies[0].stat().st_mode & 0o777 == 0o600
   await r.async_stop()
 asyncio.run(case())
