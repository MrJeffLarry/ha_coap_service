import asyncio
from aiocoap import resource, Context
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.dispatcher import async_dispatcher_send
from .const import DOMAIN

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    # Load existing devices from Registry to avoid re-discovering them
    registry = er.async_get(hass)
    known_devices = {
        entry.unique_id for entry in er.async_entries_for_config_entry(registry, entry.entry_id)
    }

    # Initialize container for our CoAP context
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        "discovered": known_devices
    }

    # CoAP Resource handling
    class CoapResource(resource.Resource):
        async def render_put(self, request):
            device_id = request.remote.host # Or extract from payload
            if device_id not in hass.data[DOMAIN][entry.entry_id]["discovered"]:
                hass.data[DOMAIN][entry.entry_id]["discovered"].add(device_id)
                # Tell sensor.py to add a new entity
                async_dispatcher_send(hass, f"{DOMAIN}_new_device", device_id)
            
            # Update existing entity
            async_dispatcher_send(hass, f"{DOMAIN}_update_{device_id}", request.payload.decode())
            return resource.Message(code=resource.CHANGED)

    # Setup CoAP Server
    root = resource.Site()
    root.add_resource(['sensors', 'data'], CoapResource())
    context = await Context.create_server_context(root, bind=('::', 5683))
    
    hass.data[DOMAIN][entry.entry_id]["coap_context"] = context
    await hass.config_entries.async_forward_entry_setups(entry, ["sensor"])
    return True
