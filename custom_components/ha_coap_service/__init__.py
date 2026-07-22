import asyncio
import datetime
import logging
import json

from aiocoap import resource, Context, error, Message
from aiocoap.numbers.contentformat import ContentFormat
from aiocoap.resource import ObservableResource, Resource
from aiocoap.numbers.codes import Code

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.dispatcher import async_dispatcher_send
from .const import DOMAIN, CO_PENDING_DEVICES, CO_DEVICES

_LOGGER = logging.getLogger(__name__)

class WhoAmI(resource.Resource):
    def __init__(self, hass, entry):
        super().__init__()
        self.hass = hass
        self.entry = entry

    async def render_get(self, request):
        _LOGGER.warning("Request: GET /WhoAmI")
        text = [f"Used protocol: {request.remote.scheme}."]
        text.append(f"Last reload {self.hass.data[DOMAIN][self.entry.entry_id]["load_time"]}")
        text.append(f"Devices {len(self.hass.data[DOMAIN][self.entry.entry_id]["discovered"])}")

        try:
            text.append(f"Request came from {request.remote.hostinfo}.")
            text.append(f"The server address used {request.remote.hostinfo_local}.")
        except error.AnonymousHost as e:
            text.append(f"Network peer: {request.remote}")

        claims = list(request.remote.authenticated_claims)
        if claims:
            text.append(
                f"Authenticated claims of the client: {', '.join(repr(c) for c in claims)}."
            )
        else:
            text.append("No claims authenticated.")

        return Message(
            payload="\n".join(text).encode("utf8"),
            content_format=ContentFormat.TEXT,
        )

# CoAP Resource handling
class CoapResource(resource.Resource):
    def __init__(self, hass, entry):
        super().__init__()
        self.hass = hass
        self.entry = entry

    async def render_put(self, request):
        try:
            # 1. Decode bytes to string and parse JSON
            raw_payload = request.payload.decode("utf-8")
            data = json.loads(raw_payload)
            # 2. Extract the field safely
            device_id = data.get("client_id")

            if not device_id:
                return Message(code=Code.BAD_REQUEST, payload=b"Missing client_id")

            if device_id not in self.hass.data[DOMAIN][self.entry.entry_id]["discovered"]:
                self.hass.data[DOMAIN][self.entry.entry_id]["discovered"].add(device_id)
                # Tell sensor.py to add a new entity
                async_dispatcher_send(self.hass, f"{DOMAIN}_new_device", data)

            # Update existing entity
            async_dispatcher_send(self.hass, f"{DOMAIN}_update_{device_id}", data)

        except (json.JSONDecodeError, UnicodeDecodeError):
            # If the payload isn"t valid JSON
            return Message(code=Code.BAD_REQUEST, payload=b"Invalid JSON")

        return Message(code=Code.CHANGED)

def jsonPare(payload):
    try:
        # 1. Decode bytes to string and parse JSON
        raw_payload = payload.decode("utf-8")
        return json.loads(raw_payload), None

    except (json.JSONDecodeError, UnicodeDecodeError):
        # If the payload isn"t valid JSON
        return None, b"could not parse json"

# If device does not exist in HA it register here or at startup
class EndpointDevice(resource.Resource):
    def __init__(self, hass, entry):
        super().__init__()
        self.hass = hass
        self.entry = entry

    # New device, get information about it and all its sensors to publich to HA
    async def render_put(self, request):
        data, err = jsonPare(request.payload)
        if err != None:
            return Message(code=Code.BAD_REQUEST, payload=err)

        device_id = data.get("device_id")
#        manufactor = data.get("manufactor")
#        sw_version = data.get("fw_version")
#        hw_version = data.get("hw_version")

        if not device_id:
            return Message(code=Code.BAD_REQUEST, payload=b"Missing device_id")

        if device_id not in self.hass.data[DOMAIN][self.entry.entry_id][CO_DEVICES]:
            # Trigger Home Assistant config flow discovery
            self.hass.async_create_task(
                self.hass.config_entries.flow.async_init(
                    DOMAIN,
                    context={"source": "coap", "device_id":device_id},
                    data=data
                )
            )
            return Message(code=Code.CREATED) # or 2.04 if you want to swallow it temporarily

#        if device_id not in self.hass.data[DOMAIN][self.entry.entry_id][CO_DEVICES]:
#            self.hass.data[DOMAIN][self.entry.entry_id][CO_DEVICES].add(device_id)
#            # Tell sensor.py to add a new entity
#            async_dispatcher_send(self.hass, f"{DOMAIN}_new_device", data)

        # Update existing entity
        async_dispatcher_send(self.hass, f"{DOMAIN}_update_{device_id}", data)

        return Message(code=Code.CHANGED)

# device send data to HA, send back register new device if not exist
class EndpointDeviceData(resource.Resource):
    def __init__(self, hass, entry):
        super().__init__()
        self.hass = hass
        self.entry = entry

# listen for device events from HA -> Device
class EndpointDeviceObserveEntity(resource.ObservableResource):
    def __init__(self, hass, entry):
        super().__init__()
        self.hass = hass
        self.entry = entry
        self.handle = None

    def notify(self):
        self.updated_state()
        self.reschedule()

    def reschedule(self):
        self.handle = asyncio.get_running_loop().call_later(5, self.notify)

    def update_observation_count(self, count):
        if count and self.handle is None:
            print("Starting the clock")
            self.reschedule()
        if count == 0 and self.handle:
            print("Stopping the clock")
            self.handle.cancel()
            self.handle = None

    async def render_get(self, request):
        payload = datetime.datetime.now().strftime("%Y-%m-%d %H:%M").encode("ascii")
        return Message(payload=payload, content_format=ContentFormat.TEXT)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    # Load existing devices from Registry to avoid re-discovering them
    registry = er.async_get(hass)
    known_devices = {
        entry.unique_id for entry in er.async_entries_for_config_entry(registry, entry.entry_id)
    }

    load_time = datetime.datetime.now(datetime.timezone.utc)

    # Store it in hass.data so the sensor can read it
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        "load_time": load_time,
        CO_PENDING_DEVICES: [],
        CO_DEVICES: known_devices,
        "discovered": known_devices,
        "instances": {}
    }

    # Setup CoAP Server
    root = resource.Site()
    root.add_resource(["whoami"], WhoAmI(hass, entry))
    root.add_resource(["device"], EndpointDevice(hass, entry))
    root.add_resource(["device", "data"], EndpointDeviceData(hass, entry))
    root.add_resource(["device", "observe"], EndpointDeviceObserveEntity(hass, entry))

    # Old
#    root.add_resource(["sensors", "data"], CoapResource(hass, entry))
#    root.add_resource(["device"], TimeResource())

    context = await Context.create_server_context(root, bind=("127.0.0.1", 5683))

    hass.data[DOMAIN][entry.entry_id]["coap_context"] = context
    await hass.config_entries.async_forward_entry_setups(entry, ["sensor"])
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    # 1. Forward the unload to the sensor platform
    unload_ok = await hass.config_entries.async_unload_platforms(entry, ["sensor"])

    # 2. Shutdown the CoAP context
    if unload_ok:
        coap_context = hass.data[DOMAIN][entry.entry_id].get("coap_context")
        if coap_context:
            await coap_context.shutdown()  # This is the critical cleanup step

        # 3. Clean up hass.data
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok










