"""Authenticated catalog protocol; no public static data endpoints."""
import voluptuous as vol
from homeassistant.components import websocket_api
from homeassistant.exceptions import Unauthorized,ServiceValidationError,HomeAssistantError
from .const import DOMAIN,MODES
from .routes import RouteActions
from .source import SourceError


def _authenticated(connection):
    if connection.user is None:
        raise Unauthorized


@websocket_api.websocket_command({'type':'google_maps_lists/catalog'})
def ws_catalog(hass,connection,msg):
    _authenticated(connection)
    runtime = hass.data[DOMAIN]
    connection.send_result(msg['id'],{**runtime.catalog.serialize(),'collection_error':runtime.collection_error})


@websocket_api.websocket_command({'type':'google_maps_lists/subscribe'})
def ws_subscribe(hass,connection,msg):
    _authenticated(connection)
    connection.subscriptions[msg['id']] = hass.data[DOMAIN].catalog.subscribe(
        lambda revision:connection.send_event(msg['id'],{'revision':revision}))
    connection.send_result(msg['id'])
    # HA automatically resubscribes on reconnect; acknowledge current state too.
    connection.send_event(msg['id'],{'revision':hass.data[DOMAIN].catalog.revision})


@websocket_api.websocket_command({'type':'google_maps_lists/route',
    vol.Required('place_id'):str,vol.Required('mode'):vol.In(MODES)})
def ws_route(hass,connection,msg):
    _authenticated(connection)
    runtime = hass.data[DOMAIN]
    try:
        url = RouteActions(hass,runtime.catalog,runtime.config).build_url(msg['place_id'],msg['mode'])
    except ServiceValidationError as err:
        connection.send_error(msg['id'],'route_unavailable',str(err))
        return
    connection.send_result(msg['id'],{'url':url})


@websocket_api.websocket_command({'type':'google_maps_lists/send_to_phone',
    vol.Required('place_id'):str,vol.Required('mode'):vol.In(MODES)})
@websocket_api.async_response
async def ws_send(hass,connection,msg):
    _authenticated(connection)
    try:
        response = await hass.services.async_call(DOMAIN,'send_to_phone',
            {'place_id':msg['place_id'],'mode':msg['mode']},blocking=True,
            context=connection.context(msg),return_response=True)
    except ServiceValidationError as err:
        connection.send_error(msg['id'],'route_unavailable',str(err))
        return
    except HomeAssistantError:
        connection.send_error(msg['id'],'notify_failed','notify_failed')
        return
    connection.send_result(msg['id'],response)


@websocket_api.websocket_command({'type':'google_maps_lists/details',
    vol.Required('place_id'):str})
@websocket_api.async_response
async def ws_details(hass,connection,msg):
    _authenticated(connection)
    try:
        result = await hass.data[DOMAIN].async_details(msg['place_id'])
    except ServiceValidationError:
        connection.send_error(msg['id'],'unknown_place','unknown_place')
        return
    except SourceError as err:
        connection.send_error(msg['id'],'details_unavailable',err.code)
        return
    connection.send_result(msg['id'],result)


def register_commands(hass,runtime):
    for command in (ws_catalog,ws_subscribe,ws_route,ws_send,ws_details):
        websocket_api.async_register_command(hass,command)
