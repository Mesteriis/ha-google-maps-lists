import asyncio
from dataclasses import replace
import pytest
import voluptuous as vol
from homeassistant.core import HomeAssistant
from custom_components.google_maps_lists.config import validate_config
from custom_components.google_maps_lists.catalog import Catalog
from test_catalog import cfg, snap, NOW


def test_labels_config_validation():
    config=validate_config({'lists':[], 'labels':{'100:200':'  Любимое место  '}})
    assert config.labels == (('100:200','Любимое место'),)
    for labels in ({'bad':'Name'},{'100:200':''},{'100:200':None},{'100:200':'x'*513}):
        with pytest.raises(vol.Invalid):validate_config({'lists':[],'labels':labels})


def test_label_projection_and_reload_preserve_source_name(tmp_path):
    async def case():
        h=HomeAssistant(str(tmp_path));c=Catalog(h,replace(cfg(),labels=(('100:200','У друзей'),)),lambda:NOW)
        await c.async_publish(snap())
        p=c.get_place('100:200');assert p['label']=='У друзей' and p['name']=='Place'
        assert 'label' not in c._state['records']['one']['snapshot']['places'][0]
        await c.async_reconfigure(cfg())
        assert 'label' not in c.get_place('100:200')
    asyncio.run(case())
