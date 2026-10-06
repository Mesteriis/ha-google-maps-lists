"""Compact catalog counts, never personal location records in Recorder."""
from homeassistant.components.sensor import SensorEntity
from .const import DOMAIN

async def async_setup_platform(hass,config,async_add_entities,discovery_info=None):
    async_add_entities([CatalogStatus(hass.data[DOMAIN])])

class CatalogStatus(SensorEntity):
    _attr_name = 'Google Maps lists'
    _attr_unique_id = 'google_maps_lists_status'
    _attr_icon = 'mdi:map-marker-multiple-outline'
    _attr_should_poll = True

    def __init__(self,runtime):
        self.runtime = runtime

    async def async_added_to_hass(self):
        self.async_on_remove(self.runtime.catalog.subscribe(lambda revision:self.async_schedule_update_ha_state(True)))

    async def async_update(self):
        catalog = self.runtime.catalog.serialize()
        self._attr_native_value = len(catalog['places'])
        self._attr_extra_state_attributes = {
            'source_count':len(catalog['groups']),
            'stale_count':sum(g['stale'] for g in catalog['groups']),
            'error_count':sum(bool(g['error']) for g in catalog['groups']),
            'collection_error':self.runtime.collection_error,
        }
