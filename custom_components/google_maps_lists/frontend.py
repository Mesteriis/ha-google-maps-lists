"""Serve only the bundled card, never YAML, cached places or notes."""
from pathlib import Path
from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.http import StaticPathConfig

async def async_register_card(hass, version):
    directory = Path(__file__).parent / 'frontend'
    await hass.http.async_register_static_paths([
        StaticPathConfig('/google_maps_lists/card', str(directory), cache_headers=False)
    ])
    add_extra_js_url(hass, f'/google_maps_lists/card/belovodie-places-card.js?v={version}')
