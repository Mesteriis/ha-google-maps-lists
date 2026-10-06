import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock,patch
from custom_components.google_maps_lists.frontend import async_register_card

def test_static_path_exposes_assets_only_and_registers_versioned_module():
 async def case():
  h=SimpleNamespace(http=SimpleNamespace(async_register_static_paths=AsyncMock()))
  with patch('custom_components.google_maps_lists.frontend.add_extra_js_url') as add:
   await async_register_card(h,'1.1.0')
   paths=h.http.async_register_static_paths.call_args.args[0]
   assert len(paths)==1 and paths[0].url_path=='/google_maps_lists/card'
   assert paths[0].path.endswith('/google_maps_lists/frontend')
   assert paths[0].cache_headers is False
   add.assert_called_once_with(h,'/google_maps_lists/card/belovodie-places-card.js?v=1.1.0')
 asyncio.run(case())
