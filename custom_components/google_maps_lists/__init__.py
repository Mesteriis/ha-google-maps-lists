"""YAML-only saved Google Maps lists integration."""
import asyncio
from datetime import datetime, UTC
from pathlib import Path
import shutil
import os
import aiohttp
import voluptuous as vol
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED, EVENT_HOMEASSISTANT_STOP
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.discovery import async_load_platform
from homeassistant.helpers.service import async_register_admin_service
from .catalog import Catalog
from .config import validate_config
from .const import DOMAIN
from .runtime import Runtime
from .source import GoogleListSource


def _yaml_schema(value):
    validate_config(value)
    return value

CONFIG_SCHEMA = vol.Schema({vol.Optional(DOMAIN):_yaml_schema},extra=vol.ALLOW_EXTRA)


def _preserve_corrupt(path):
    if Path(path).exists():
        copy = f'{path}.invalid-{datetime.now(UTC).strftime("%Y%m%d%H%M%S")}'
        shutil.copy2(path,copy)
        os.chmod(copy,0o600)


async def async_setup(hass,config):
    if DOMAIN not in config or DOMAIN in hass.data:
        return True
    from .frontend import async_register_card
    await async_register_card(hass, '1.1.2')
    definition = validate_config(config[DOMAIN])
    catalog = Catalog(hass,definition)
    try:
        await catalog.async_load()
    except (ValueError,OSError):
        await hass.async_add_executor_job(_preserve_corrupt,catalog.store.path)
        # Keep explicit unavailability without overwriting the invalid original.
        for row in definition.lists:
            catalog._state['records'][row.id] = {'fingerprint':__import__('hashlib').sha256(row.url.encode()).hexdigest(),
                'snapshot':None,'error':'cache_invalid'}
    session = aiohttp.ClientSession(cookie_jar=aiohttp.DummyCookieJar(),trust_env=False)
    runtime = Runtime(hass,definition,catalog,GoogleListSource(session))
    runtime.session = session
    hass.data[DOMAIN] = runtime
    from .websocket import register_commands
    register_commands(hass,runtime)
    async def reload(call):
        try:
            await runtime.async_reload()
        except (ValueError,vol.Invalid,OSError) as err:
            raise ServiceValidationError('Google Maps YAML reload failed') from err
    async def refresh(call):
        await runtime.async_refresh(manual=True)
    async_register_admin_service(hass,DOMAIN,'reload',reload)
    async_register_admin_service(hass,DOMAIN,'refresh',refresh)
    from .routes import register_route_service
    register_route_service(hass,runtime)
    runtime.schedule()
    runtime.cancel_start = hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED,runtime.start)
    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP,runtime.async_stop)
    await async_load_platform(hass,'sensor',DOMAIN,{},config)
    if hass.is_running:
        runtime.start()
    return True
