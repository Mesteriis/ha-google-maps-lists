"""Backend route authority and fixed Companion target."""
from urllib.parse import urlencode
import voluptuous as vol
from homeassistant.core import SupportsResponse
from homeassistant.exceptions import ServiceValidationError
from .const import DOMAIN,MODES
from .models import valid_coordinates

ACTION_SCHEMA = vol.Schema({vol.Required('place_id'):str,vol.Required('mode'):vol.In(MODES)})

class RouteActions:
    def __init__(self,hass,catalog,config):
        self.hass,self.catalog,self.config = hass,catalog,config

    def build_url(self,place_id,mode):
        if mode not in MODES:
            raise ServiceValidationError('unknown_mode')
        place = self.catalog.get_place(place_id)
        if place is None:
            raise ServiceValidationError('unknown_place')
        if not valid_coordinates(place['latitude'],place['longitude']):
            raise ServiceValidationError('place_has_no_coordinates')
        home = self.hass.states.get(self.config.route_origin)
        if home is None or home.state in ('unknown','unavailable') or not valid_coordinates(home.attributes.get('latitude'),home.attributes.get('longitude')):
            raise ServiceValidationError('home_unavailable')
        query = {'api':1,'origin':f"{home.attributes['latitude']},{home.attributes['longitude']}",
            'destination':f"{place['latitude']},{place['longitude']}",'travelmode':mode}
        return 'https://www.google.com/maps/dir/?'+urlencode(query)

    async def async_send(self,place_id,mode,context=None):
        url = self.build_url(place_id,mode)
        domain,service = self.config.notify_service.split('.',1)
        if not self.hass.services.has_service(domain,service):
            raise ServiceValidationError('notify_unavailable')
        try:
            await self.hass.services.async_call(domain,service,{
                'title':'Маршрут из дома','message':self.catalog.get_place(place_id)['name'],
                'data':{'tag':'belovodie-saved-place-route','url':url,'clickAction':url,
                    'actions':[{'action':'URI','title':'Google Maps','uri':url}]}},
                blocking=True,context=context)
        except Exception as err:
            raise ServiceValidationError('notify_failed') from err


def register_route_service(hass,runtime):
    async def send(call):
        await RouteActions(hass,runtime.catalog,runtime.config).async_send(
            call.data['place_id'],call.data['mode'],context=call.context)
        return {'accepted':True}
    hass.services.async_register(DOMAIN,'send_to_phone',send,schema=ACTION_SCHEMA,
                                 supports_response=SupportsResponse.OPTIONAL)
